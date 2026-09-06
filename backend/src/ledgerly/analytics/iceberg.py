"""Iceberg writes via Athena MERGE INTO (ADR 0001).

Three mutations make up a sync, and all three must be idempotent (SPEC §41):

  1. upsert   — added + modified transactions, matched on transaction_id
  2. supersede— a POSTED transaction carrying pending_transaction_id retires the
                PENDING row it replaces
  3. remove   — Plaid's `removed` list is tombstoned, never hard-deleted

Rows are passed inline as `USING (VALUES ...)`. At personal scale a sync is
hundreds of rows, and inline values avoid a staging table plus its own create/
drop/cleanup failure modes. Batching keeps each statement inside Athena's
262 144-byte query limit.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from ledgerly.analytics.athena import AthenaClient
from ledgerly.models import Transaction, TransferGroup, TransferStatus

logger = logging.getLogger(__name__)

# ~400 bytes per rendered row; 400 rows leaves generous headroom under Athena's
# 262 144-byte statement cap even for long merchant descriptions.
MERGE_BATCH_SIZE = 400

# Column order is shared by the VALUES alias, the UPDATE SET list, and the
# INSERT list, so it is defined once. Any schema change edits this tuple only.
COLUMNS: tuple[str, ...] = (
    "transaction_id", "account_id", "item_id",
    "transaction_date", "authorized_date",
    "amount", "iso_currency_code",
    "description", "merchant_name", "merchant_entity_id",
    "plaid_category_primary", "plaid_category_detailed", "plaid_category_confidence",
    "payment_channel", "transaction_code",
    "is_pending", "status", "pending_transaction_id",
    "normalized_merchant", "category", "subcategory",
    "transaction_type", "is_transfer", "transfer_group_id", "is_recurring",
    "user_category_override", "user_type_override", "user_note",
    "_ingested_at", "_processed_at", "_source_key", "_sync_cursor",
)


def sql_literal(value: Any) -> str:
    """Render a Python value as a typed SQL literal.

    Every string is single-quote escaped. Values originate from Plaid rather
    than end users, but a merchant name containing an apostrophe ("Trader Joe's"
    — which appears in real data) would otherwise break the statement, and the
    same escaping closes the injection path.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return f"DECIMAL '{value}'"
    if isinstance(value, datetime):
        return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}'"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _row_values(txn: Transaction) -> str:
    values = (
        txn.transaction_id, txn.account_id, txn.item_id,
        txn.transaction_date, txn.authorized_date,
        txn.amount, txn.iso_currency_code,
        txn.description, txn.merchant_name, txn.merchant_entity_id,
        txn.plaid_category_primary, txn.plaid_category_detailed,
        txn.plaid_category_confidence,
        txn.payment_channel, txn.transaction_code,
        txn.is_pending, str(txn.status), txn.pending_transaction_id,
        txn.normalized_merchant, txn.category, txn.subcategory,
        str(txn.transaction_type), txn.is_transfer, txn.transfer_group_id,
        txn.is_recurring,
        txn.user_category_override, txn.user_type_override, txn.user_note,
        txn.ingested_at, txn.processed_at, txn.source_key, txn.sync_cursor,
    )
    return "(" + ", ".join(sql_literal(v) for v in values) + ")"


class IcebergWriter:
    def __init__(self, client: AthenaClient, database: str) -> None:
        self._client = client
        self._db = database

    @property
    def _table(self) -> str:
        return f"{self._db}.transactions"

    # ── 1. Upsert ───────────────────────────────────────────────────────────

    def upsert(self, transactions: list[Transaction]) -> int:
        """Insert new transactions and update existing ones.

        Matching on transaction_id makes a replayed sync a no-op rather than a
        duplicate — the property the whole ingestion design depends on.
        """
        if not transactions:
            return 0

        written = 0
        for start in range(0, len(transactions), MERGE_BATCH_SIZE):
            batch = transactions[start : start + MERGE_BATCH_SIZE]
            self._client.execute(self._merge_sql(batch))
            written += len(batch)
            logger.info("iceberg_upsert batch=%d total=%d", len(batch), written)
        return written

    def _merge_sql(self, batch: list[Transaction]) -> str:
        columns = ", ".join(COLUMNS)
        values = ",\n    ".join(_row_values(t) for t in batch)

        # User overrides are preserved on update. Re-running enrichment must
        # never clobber a manual correction — that is what makes "rebuild the
        # curated layer from raw" safe (SPEC §15).
        # Excluded from the generic assignment loop because each is either the
        # match key or is assigned explicitly below with override-preservation.
        # Listing one in both places produces DUPLICATE_COLUMN_NAME.
        protected = {
            "transaction_id",
            "category", "subcategory", "transaction_type",
            "user_note", "user_category_override", "user_type_override",
        }
        updates = ",\n        ".join(
            f"{c} = s.{c}" for c in COLUMNS if c not in protected
        )
        # A user-set category survives; otherwise take the incoming value.
        updates += """,
        category = IF(t.user_category_override, t.category, s.category),
        subcategory = IF(t.user_category_override, t.subcategory, s.subcategory),
        transaction_type = IF(t.user_type_override, t.transaction_type, s.transaction_type),
        user_note = t.user_note,
        user_category_override = t.user_category_override,
        user_type_override = t.user_type_override"""

        return f"""
MERGE INTO {self._table} t
USING (VALUES
    {values}
) AS s ({columns})
ON t.transaction_id = s.transaction_id
WHEN MATCHED THEN UPDATE SET
        {updates}
WHEN NOT MATCHED THEN INSERT ({columns})
    VALUES ({", ".join(f"s.{c}" for c in COLUMNS)})
""".strip()

    # ── 2. Supersede pending ────────────────────────────────────────────────

    def supersede_pending(self, transactions: list[Transaction]) -> int:
        """Tombstone PENDING rows replaced by a POSTED transaction.

        Plaid assigns a posted transaction a DIFFERENT transaction_id from the
        pending one it replaces, linking them via pending_transaction_id.
        Without this step both rows survive and every pending charge is counted
        twice — the single most likely way this pipeline could corrupt
        spending totals (SPEC §14).
        """
        superseded = [
            t.pending_transaction_id
            for t in transactions
            if t.pending_transaction_id and not t.is_pending
        ]
        if not superseded:
            return 0

        ids = ", ".join(sql_literal(i) for i in superseded)
        self._client.execute(
            f"""
UPDATE {self._table}
SET status = 'REMOVED', _processed_at = {sql_literal(datetime.utcnow())}
WHERE transaction_id IN ({ids}) AND status != 'REMOVED'
""".strip()
        )
        logger.info("iceberg_superseded count=%d", len(superseded))
        return len(superseded)

    # ── 3. Remove ───────────────────────────────────────────────────────────

    def remove(self, transaction_ids: list[str]) -> int:
        """Tombstone transactions Plaid reports as removed.

        Deliberately an UPDATE, not a DELETE: a removal is itself a fact about
        the account's history, and hard-deleting would make the curated layer
        unable to explain a balance change that already happened.
        """
        if not transaction_ids:
            return 0

        removed = 0
        for start in range(0, len(transaction_ids), MERGE_BATCH_SIZE):
            batch = transaction_ids[start : start + MERGE_BATCH_SIZE]
            ids = ", ".join(sql_literal(i) for i in batch)
            self._client.execute(
                f"""
UPDATE {self._table}
SET status = 'REMOVED', _processed_at = {sql_literal(datetime.utcnow())}
WHERE transaction_id IN ({ids})
""".strip()
            )
            removed += len(batch)
        logger.info("iceberg_removed count=%d", removed)
        return removed


# ── Transfer groups ─────────────────────────────────────────────────────────

TRANSFER_COLUMNS: tuple[str, ...] = (
    "transfer_group_id",
    "source_transaction_id", "source_account_id",
    "destination_transaction_id", "destination_account_id",
    "amount", "iso_currency_code",
    "transfer_kind", "status", "confidence", "match_method", "date_gap_days",
    "source_date", "destination_date",
    "matched_at", "confirmed_at", "confirmed_by", "_processed_at",
)


class TransferWriter:
    """Persists matched pairs and flags their legs (SPEC §17).

    Two writes, in this order:
      1. the group rows, so the pairing itself is recorded
      2. the transaction legs, flipped to TRANSFER so they leave the
         income/expense totals

    If step 2 failed alone, the groups would exist while spending stayed
    overstated — visible and repairable by re-running. The reverse order could
    leave legs marked as transfers with no group explaining why, which is
    strictly worse because nothing would point at the problem.
    """

    def __init__(self, client: AthenaClient, database: str) -> None:
        self._client = client
        self._db = database

    def upsert_groups(self, groups: list[TransferGroup]) -> int:
        if not groups:
            return 0

        written = 0
        for start in range(0, len(groups), MERGE_BATCH_SIZE):
            batch = groups[start : start + MERGE_BATCH_SIZE]
            values = ",\n    ".join(
                "("
                + ", ".join(
                    sql_literal(v)
                    for v in (
                        g.transfer_group_id,
                        g.source_transaction_id, g.source_account_id,
                        g.destination_transaction_id, g.destination_account_id,
                        g.amount, g.iso_currency_code,
                        str(g.transfer_kind), str(g.status), g.confidence,
                        str(g.match_method), g.date_gap_days,
                        g.source_date, g.destination_date,
                        g.matched_at, g.confirmed_at, g.confirmed_by,
                        datetime.utcnow(),
                    )
                )
                + ")"
                for g in batch
            )
            columns = ", ".join(TRANSFER_COLUMNS)
            # A user decision must survive re-detection: if someone rejected a
            # pair, the matcher proposing it again must not silently re-confirm
            # it. Only non-REJECTED groups are updated.
            updates = ",\n        ".join(
                f"{c} = s.{c}" for c in TRANSFER_COLUMNS if c != "transfer_group_id"
            )
            self._client.execute(f"""
MERGE INTO {self._db}.transfer_groups t
USING (VALUES
    {values}
) AS s ({columns})
ON t.transfer_group_id = s.transfer_group_id
WHEN MATCHED AND t.status != 'REJECTED' THEN UPDATE SET
        {updates}
WHEN NOT MATCHED THEN INSERT ({columns})
    VALUES ({", ".join(f"s.{c}" for c in TRANSFER_COLUMNS)})
""".strip())
            written += len(batch)
        logger.info("transfer_groups_written count=%d", written)
        return written

    def mark_legs(self, groups: list[TransferGroup]) -> int:
        """Flip confirmed legs to TRANSFER so they drop out of income/expense.

        Only CONFIRMED groups. A SUGGESTED pair still shows as two ordinary
        transactions — money is never removed from the totals on a guess.
        """
        confirmed = [g for g in groups if g.status is TransferStatus.CONFIRMED]
        if not confirmed:
            return 0

        leg_ids: list[str] = []
        for g in confirmed:
            leg_ids += [g.source_transaction_id, g.destination_transaction_id]

        for start in range(0, len(leg_ids), MERGE_BATCH_SIZE):
            batch = leg_ids[start : start + MERGE_BATCH_SIZE]
            ids = ", ".join(sql_literal(i) for i in batch)
            # user_type_override is respected: a manual classification wins over
            # automatic detection.
            self._client.execute(f"""
UPDATE {self._db}.transactions
SET is_transfer = true,
    transaction_type = 'TRANSFER',
    _processed_at = {sql_literal(datetime.utcnow())}
WHERE transaction_id IN ({ids})
  AND status != 'REMOVED'
  AND user_type_override = false
""".strip())

        # transfer_group_id is set per group so each leg points at its pair.
        for g in confirmed:
            ids = ", ".join(
                sql_literal(i)
                for i in (g.source_transaction_id, g.destination_transaction_id)
            )
            self._client.execute(f"""
UPDATE {self._db}.transactions
SET transfer_group_id = {sql_literal(g.transfer_group_id)}
WHERE transaction_id IN ({ids}) AND user_type_override = false
""".strip())

        logger.info("transfer_legs_marked groups=%d legs=%d", len(confirmed), len(leg_ids))
        return len(leg_ids)

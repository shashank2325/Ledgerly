"""Run transfer detection over the curated layer and persist the results.

Reads candidates back out of Iceberg rather than working from the sync payload,
because a transfer's two legs often arrive in DIFFERENT syncs — the checking
side may post today and the savings side tomorrow, and they may belong to
different Plaid items entirely. Detection therefore has to see the whole
account set at once (ADR 0005).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from ledgerly.analytics import AthenaClient, TransferWriter
from ledgerly.models import Account, AccountType, Transaction, TransactionType
from ledgerly.pipeline.transfers import find_transfers

logger = logging.getLogger(__name__)

# How far back to reconsider. Detection is idempotent, so a wide window is safe;
# 90 days keeps the scan small while covering any leg that arrived late.
DEFAULT_LOOKBACK_DAYS = 90


def _to_transaction(row: dict[str, Any]) -> Transaction:
    return Transaction(
        transaction_id=row["transaction_id"],
        account_id=row["account_id"],
        item_id=row.get("item_id") or "",
        transaction_date=date.fromisoformat(row["transaction_date"]),
        amount=Decimal(str(row["amount"])),
        iso_currency_code=row.get("iso_currency_code") or "USD",
        description=row.get("description") or "",
        plaid_category_primary=row.get("plaid_category_primary"),
        transaction_code=row.get("transaction_code"),
        transaction_type=TransactionType(row.get("transaction_type") or "UNKNOWN"),
        is_transfer=bool(row.get("is_transfer")),
    )


def detect_and_persist(
    client: AthenaClient,
    database: str,
    accounts: list[Account],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    since = (datetime.now(UTC).date() - timedelta(days=lookback_days)).isoformat()

    rows = client.query(f"""
        SELECT transaction_id, account_id, item_id, transaction_date, amount,
               iso_currency_code, description, plaid_category_primary,
               transaction_code, transaction_type, is_transfer
        FROM {database}.transactions
        WHERE status != 'REMOVED'
          AND is_transfer = false
          AND transaction_date >= DATE '{since}'
    """)

    transactions = [_to_transaction(r) for r in rows]
    account_map = {a.account_id: a for a in accounts}

    groups = find_transfers(transactions, account_map)

    writer = TransferWriter(client, database)
    written = writer.upsert_groups(groups)
    legs = writer.mark_legs(groups)

    confirmed = [g for g in groups if g.status.value == "CONFIRMED"]
    suggested = [g for g in groups if g.status.value == "SUGGESTED"]

    result = {
        "scanned": len(transactions),
        "groups_found": len(groups),
        "confirmed": len(confirmed),
        "suggested": len(suggested),
        "legs_marked": legs,
        "groups_written": written,
        "amount_reclassified": str(sum((g.amount for g in confirmed), Decimal("0"))),
        "by_kind": {
            kind: sum(1 for g in confirmed if g.transfer_kind.value == kind)
            for kind in {g.transfer_kind.value for g in confirmed}
        },
        "lookback_days": lookback_days,
    }
    logger.info("transfer_detection_complete %s", result)
    return result

"""Read queries backing the Ledger and Overview pages.

Athena, not DynamoDB. SPEC §8 warns against using Athena for every operational
read, and the guard is the WHERE clause: these are always bounded by a date
range or a LIMIT, so each query scans one or two monthly partitions rather than
the whole table.

Money is returned as STRINGS. It crosses the wire exactly, and JavaScript never
sees a float — 0.1 + 0.2 !== 0.3 is not an acceptable property for a ledger.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any

from ledgerly.analytics.athena import AthenaClient
from ledgerly.analytics.iceberg import sql_literal

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

TXN_COLUMNS = """
    transaction_id, account_id, item_id, transaction_date, authorized_date,
    amount, iso_currency_code, description, merchant_name, normalized_merchant,
    category, subcategory, plaid_category_primary, transaction_type, status,
    is_pending, is_transfer, transfer_group_id, is_recurring,
    user_category_override, user_note
"""


def _row_to_json(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a row for the API. Mirrors the frontend `Transaction` type."""
    return {
        "transaction_id": row["transaction_id"],
        "account_id": row["account_id"],
        "item_id": row.get("item_id") or "",
        "transaction_date": row["transaction_date"],
        "authorized_date": row.get("authorized_date"),
        "amount": str(row["amount"]),
        "iso_currency_code": row.get("iso_currency_code") or "USD",
        "description": row.get("description") or "",
        "merchant_name": row.get("merchant_name"),
        "normalized_merchant": row.get("normalized_merchant"),
        "category": row.get("category"),
        "subcategory": row.get("subcategory"),
        "plaid_category_primary": row.get("plaid_category_primary"),
        "transaction_type": row.get("transaction_type") or "UNKNOWN",
        "status": row.get("status") or "POSTED",
        "is_pending": bool(row.get("is_pending")),
        "is_transfer": bool(row.get("is_transfer")),
        "transfer_group_id": row.get("transfer_group_id"),
        "is_recurring": bool(row.get("is_recurring")),
        "user_category_override": bool(row.get("user_category_override")),
        "user_note": row.get("user_note"),
    }


def list_transactions(
    client: AthenaClient,
    database: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    account_id: str | None = None,
    category: str | None = None,
    transaction_type: str | None = None,
    search: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Transactions plus any transfer groups whose legs appear in the result.

    The groups are fetched alongside so the client can render a matched pair as
    one joined row without a second round trip.
    """
    limit = max(1, min(limit, MAX_LIMIT))

    where = ["status != 'REMOVED'"]
    if date_from:
        where.append(f"transaction_date >= DATE {sql_literal(date_from)}")
    if date_to:
        where.append(f"transaction_date <= DATE {sql_literal(date_to)}")
    if account_id:
        where.append(f"account_id = {sql_literal(account_id)}")
    if category:
        where.append(f"category = {sql_literal(category)}")
    if transaction_type:
        where.append(f"transaction_type = {sql_literal(transaction_type)}")
    if search:
        # Case-insensitive substring across the fields a person would search.
        # sql_literal escapes the value, so a quote in the term is inert.
        needle = sql_literal(f"%{search.lower()}%")
        where.append(
            "(lower(description) LIKE " + needle
            + " OR lower(coalesce(normalized_merchant, '')) LIKE " + needle
            + " OR lower(coalesce(category, '')) LIKE " + needle + ")"
        )

    clause = " AND ".join(where)
    rows = client.query(f"""
        SELECT {TXN_COLUMNS}
        FROM {database}.transactions
        WHERE {clause}
        ORDER BY transaction_date DESC, transaction_id
        LIMIT {limit}
    """)

    transactions = [_row_to_json(r) for r in rows]

    group_ids = {t["transfer_group_id"] for t in transactions if t["transfer_group_id"]}
    groups: list[dict[str, Any]] = []
    if group_ids:
        ids = ", ".join(sql_literal(g) for g in group_ids)
        groups = [
            {
                "transfer_group_id": g["transfer_group_id"],
                "source_transaction_id": g["source_transaction_id"],
                "source_account_id": g["source_account_id"],
                "destination_transaction_id": g["destination_transaction_id"],
                "destination_account_id": g["destination_account_id"],
                "amount": str(g["amount"]),
                "transfer_kind": g["transfer_kind"],
                "status": g["status"],
                "confidence": str(g["confidence"]),
                "date_gap_days": int(g["date_gap_days"] or 0),
            }
            for g in client.query(f"""
                SELECT transfer_group_id, source_transaction_id, source_account_id,
                       destination_transaction_id, destination_account_id, amount,
                       transfer_kind, status, confidence, date_gap_days
                FROM {database}.transfer_groups
                WHERE transfer_group_id IN ({ids})
            """)
        ]

    return {"transactions": transactions, "transfer_groups": groups, "count": len(transactions)}


def net_worth_series(
    client: AthenaClient,
    database: str,
    *,
    current_net_worth: Decimal,
    today: str,
    months: int = 12,
) -> list[dict[str, str]]:
    """Reconstruct net worth over time by walking transaction flow backwards.

    We do not have a balance history: Plaid reports only the CURRENT balance,
    and the accounts_snapshot table that would capture it daily is not yet being
    populated. Rather than draw nothing — or worse, invent a shape — this
    derives the series from data we actually hold:

        net worth at end of month M = current net worth
                                      − (net flow of every transaction after M)

    Every point is therefore computed from real transactions.

    LIMITATION, stated plainly: this is exact for cash and credit accounts,
    where balance moves only when a transaction occurs. It is approximate for
    investments, whose balance also moves with the market — a 401k that gained
    value without any transaction will appear flat. The series is a cash-flow
    reconstruction, not a mark-to-market history, and the UI labels it as a
    trend rather than a balance record.

    Transfers are excluded: moving money between your own accounts nets to zero
    and must not move the line.
    """
    rows = client.query(f"""
        SELECT date_format(transaction_date, '%Y-%m') AS month,
               sum(amount) AS net_flow
        FROM {database}.transactions
        WHERE status != 'REMOVED'
          AND transaction_type != 'TRANSFER'
          AND transaction_date >= date_add('month', -{months}, DATE {sql_literal(today)})
        GROUP BY date_format(transaction_date, '%Y-%m')
        ORDER BY month
    """)
    if not rows:
        return []

    # Walk backwards. Each point is the balance at the END of its month: the
    # latest month is today's figure, and each earlier month is recovered by
    # undoing the later month's flow.
    #
    # The label must be attached BEFORE subtracting, not after — subtracting
    # month M's flow yields the end of month M-1, so labelling the result M
    # shifts the whole series a month and duplicates the final point.
    series: list[dict[str, str]] = []
    running = current_net_worth
    for row in reversed(rows):
        series.append({"date": row["month"], "value": str(running)})
        running -= row["net_flow"] or Decimal("0")

    series.reverse()
    return series


def dashboard(
    client: AthenaClient, database: str, *, month_start: str, today: str
) -> dict[str, Any]:
    """Overview figures. One query per panel, each partition-bounded."""
    # Athena carries a fixed ~1.5s planning cost per query, which dominates
    # entirely at this data size — the scans themselves are milliseconds. Run
    # sequentially these four cost ~6s and the page feels broken; issued
    # concurrently they cost about as much as the slowest one. boto3 clients are
    # thread-safe for this usage, and four threads is well within Lambda's
    # budget.
    def _month_totals() -> list[dict[str, Any]]:
        return client.query(f"""
        SELECT transaction_type, sum(abs(amount)) AS total, count(*) AS n
        FROM {database}.transactions
        WHERE status != 'REMOVED'
          AND transaction_type IN ('INCOME', 'EXPENSE')
          AND transaction_date BETWEEN DATE {sql_literal(month_start)} AND DATE {sql_literal(today)}
        GROUP BY transaction_type
    """)

    def _transfers() -> list[dict[str, Any]]:
        return client.query(f"""
        SELECT coalesce(sum(abs(amount)), 0) AS total
        FROM {database}.transactions
        WHERE status != 'REMOVED' AND transaction_type = 'TRANSFER'
          AND amount < 0
          AND transaction_date BETWEEN DATE {sql_literal(month_start)} AND DATE {sql_literal(today)}
    """)

    def _cash_flow() -> list[dict[str, Any]]:
        return client.query(f"""
        SELECT date_format(transaction_date, '%Y-%m') AS month,
               sum(CASE WHEN transaction_type = 'INCOME'  THEN abs(amount) ELSE 0 END) AS income,
               sum(CASE WHEN transaction_type = 'EXPENSE' THEN abs(amount) ELSE 0 END) AS expenses
        FROM {database}.transactions
        WHERE status != 'REMOVED' AND transaction_date >= date_add('month', -11, DATE {sql_literal(today)})
        GROUP BY date_format(transaction_date, '%Y-%m')
        ORDER BY month
    """)

    def _by_category() -> list[dict[str, Any]]:
        return client.query(f"""
        SELECT category, sum(abs(amount)) AS total, count(*) AS n
        FROM {database}.transactions
        WHERE status != 'REMOVED' AND transaction_type = 'EXPENSE'
          AND transaction_date BETWEEN DATE {sql_literal(month_start)} AND DATE {sql_literal(today)}
        GROUP BY category ORDER BY total DESC LIMIT 8
    """)

    with ThreadPoolExecutor(max_workers=4) as pool:
        month_f = pool.submit(_month_totals)
        transfers_f = pool.submit(_transfers)
        cash_flow_f = pool.submit(_cash_flow)
        category_f = pool.submit(_by_category)
        month = month_f.result()
        transfers = transfers_f.result()
        cash_flow = cash_flow_f.result()
        by_category = category_f.result()

    totals = {r["transaction_type"]: (r["total"] or Decimal("0")) for r in month}
    income = totals.get("INCOME", Decimal("0"))
    spending = totals.get("EXPENSE", Decimal("0"))

    return {
        "month_income": str(income),
        "month_spending": str(spending),
        "month_net": str(income - spending),
        "month_transfers": str(transfers[0]["total"] if transfers else Decimal("0")),
        "cash_flow": [
            {
                "month": r["month"],
                "income": str(r["income"] or 0),
                "expenses": str(-(r["expenses"] or 0)),
                "net": str((r["income"] or 0) - (r["expenses"] or 0)),
            }
            for r in cash_flow
        ],
        "spending_by_category": [
            {
                "category": r["category"] or "Uncategorized",
                "amount": str(-(r["total"] or 0)),
                "transaction_count": int(r["n"] or 0),
            }
            for r in by_category
        ],
    }

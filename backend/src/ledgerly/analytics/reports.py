"""Report queries over the curated Iceberg layer.

All aggregation happens in Athena, not in Python and certainly not in the
browser: the backend is the source of truth for financial calculations
(SPEC §3, §47.9).

Every query filters `status != 'REMOVED'` and excludes TRANSFER, so no report
can double-count money moved between the user's own accounts (SPEC §19).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ledgerly.analytics.athena import AthenaClient

logger = logging.getLogger(__name__)

# Beyond this, categories are folded into "Other" — a Sankey with thirty
# ribbons communicates nothing.
MAX_CATEGORIES = 8


def _humanize(category: str | None) -> str:
    """Plaid categories arrive as GENERAL_MERCHANDISE. Render them readably
    without inventing a mapping table we would have to maintain."""
    if not category:
        return "Uncategorized"
    return category.replace("_", " ").title()


@dataclass
class CashFlowReport:
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal
    income_by_category: list[dict[str, Any]]
    expense_by_category: list[dict[str, Any]]
    date_from: str
    date_to: str

    @property
    def savings_rate(self) -> Decimal:
        """Share of income not spent. Zero income means no meaningful rate —
        return 0 rather than dividing by zero or reporting 100%."""
        if self.total_income <= 0:
            return Decimal("0")
        return (self.net_income / self.total_income * 100).quantize(Decimal("0.1"))

    def to_sankey(self) -> dict[str, Any]:
        """Shape the report as nodes and links for the Sankey.

        Three columns: income sources -> Income -> destinations (Net Income and
        expense categories). Deliberately not a general multi-level Sankey — the
        money story is 'what came in, what it became', and extra levels dilute it.
        """
        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []

        def node(node_id: str, label: str, value: Decimal, kind: str, column: int) -> str:
            nodes.append(
                {"id": node_id, "label": label, "value": str(value),
                 "kind": kind, "column": column}
            )
            return node_id

        node("income", "Income", self.total_income, "income", 1)

        # Column 0 — where money came from.
        for row in self.income_by_category:
            source_id = f"src:{row['category']}"
            node(source_id, _humanize(row["category"]), row["amount"], "income", 0)
            links.append({"source": source_id, "target": "income",
                          "value": str(row["amount"]), "kind": "income"})

        # Column 2 — what it became. Net income first: it is the number that
        # matters, and placing it top-right is where the eye lands.
        if self.net_income > 0:
            node("net", "Net Income", self.net_income, "net", 2)
            links.append({"source": "income", "target": "net",
                          "value": str(self.net_income), "kind": "net"})

        for row in self.expense_by_category:
            target_id = f"exp:{row['category']}"
            node(target_id, _humanize(row["category"]), row["amount"], "expense", 2)
            links.append({"source": "income", "target": target_id,
                          "value": str(row["amount"]), "kind": "expense"})

        return {"nodes": nodes, "links": links}


def cash_flow(
    client: AthenaClient, *, date_from: str, date_to: str
) -> CashFlowReport:
    """Income and expense totals plus per-category breakdowns for a window."""
    # Amounts are stored signed (negative = money out), so expenses are negated
    # here to report positive magnitudes.
    rows = client.query(f"""
        SELECT
            transaction_type,
            category,
            count(*)               AS txn_count,
            sum(abs(amount))       AS total
        FROM transactions
        WHERE status != 'REMOVED'
          AND transaction_type IN ('INCOME', 'EXPENSE', 'REFUND')
          AND transaction_date BETWEEN DATE '{date_from}' AND DATE '{date_to}'
        GROUP BY transaction_type, category
        ORDER BY total DESC
    """)

    income: list[dict[str, Any]] = []
    expense: list[dict[str, Any]] = []
    for row in rows:
        entry = {
            "category": row["category"],
            "amount": row["total"] or Decimal("0"),
            "count": row["txn_count"],
        }
        # A refund is money returning, so it belongs on the income side rather
        # than as negative spending — otherwise a large refund can make a
        # category's spend appear negative.
        if row["transaction_type"] in ("INCOME", "REFUND"):
            income.append(entry)
        else:
            expense.append(entry)

    def collapse(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(entries) <= MAX_CATEGORIES:
            return entries
        head, tail = entries[:MAX_CATEGORIES], entries[MAX_CATEGORIES:]
        return head + [{
            "category": "OTHER",
            "amount": sum((e["amount"] for e in tail), Decimal("0")),
            "count": sum(e["count"] for e in tail),
        }]

    total_income = sum((e["amount"] for e in income), Decimal("0"))
    total_expenses = sum((e["amount"] for e in expense), Decimal("0"))

    return CashFlowReport(
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=total_income - total_expenses,
        income_by_category=collapse(income),
        expense_by_category=collapse(expense),
        date_from=date_from,
        date_to=date_to,
    )

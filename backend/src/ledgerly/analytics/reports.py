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
    def savings_rate(self) -> Decimal | None:
        """Share of income not spent, or None when the figure is meaningless.

        The ratio is only interpretable when income is the dominant term. With
        $33.76 of income against $63,896 of spending it evaluates to
        -189,167%, which is arithmetically correct and communicates nothing —
        the reader learns less than from the two raw numbers.

        Returning None lets the UI show "—" instead of a figure that looks like
        a rendering bug. The threshold is deliberately generous: spending up to
        10x income still yields a rate (-900%), which is extreme but readable.
        """
        if self.total_income <= 0:
            return None
        if self.total_expenses > self.total_income * 10:
            return None
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

    # Refunds NET AGAINST their own category rather than counting as income.
    # A $500 airline credit did not earn you $500 — it reduced what that trip
    # cost. Reporting it as income would inflate both income and spending by
    # the same amount and make the savings rate meaningless.
    income: list[dict[str, Any]] = []
    expense_by_category: dict[str | None, dict[str, Any]] = {}
    refunds: dict[str | None, Decimal] = {}

    for row in rows:
        amount = row["total"] or Decimal("0")
        category = row["category"]
        if row["transaction_type"] == "INCOME":
            income.append({"category": category, "amount": amount, "count": row["txn_count"]})
        elif row["transaction_type"] == "REFUND":
            refunds[category] = refunds.get(category, Decimal("0")) + amount
        else:
            entry = expense_by_category.setdefault(
                category, {"category": category, "amount": Decimal("0"), "count": 0}
            )
            entry["amount"] += amount
            entry["count"] += row["txn_count"]

    for category, refunded in refunds.items():
        entry = expense_by_category.setdefault(
            category, {"category": category, "amount": Decimal("0"), "count": 0}
        )
        entry["amount"] -= refunded

    # A category refunded to zero (or below) contributed no spending; dropping
    # it avoids a zero-width Sankey ribbon and a meaningless row. Over-refunds
    # are clamped rather than rendered as negative spending, which a Sankey
    # cannot express.
    expense = sorted(
        (e for e in expense_by_category.values() if e["amount"] > 0),
        key=lambda e: e["amount"],
        reverse=True,
    )
    income.sort(key=lambda e: e["amount"], reverse=True)

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

"""The normalized transaction — the core domain object.

Mirrors `data/schemas/finance_transactions.sql`. Read that file for the full
field-by-field rationale; the invariants that code must uphold are restated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class TransactionType(StrEnum):
    """SPEC §19. The field every financial report must respect.

    TRANSFER is excluded from both income and expense totals. Getting this wrong
    is the double-counting bug that competing products ship with.
    """

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"
    UNKNOWN = "UNKNOWN"


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    # Plaid told us the transaction no longer exists. We tombstone rather than
    # hard-delete: a removal is itself a fact about the account's history.
    REMOVED = "REMOVED"


@dataclass(slots=True)
class Transaction:
    """A single normalized transaction.

    Amount sign convention: **negative leaves the account, positive enters it.**
    This is flipped from Plaid's raw convention, exactly once, in
    `pipeline.normalize`. Everything downstream sees only the normalized form.
    """

    # ── Identity ────────────────────────────────────────────────────────────
    transaction_id: str
    account_id: str
    item_id: str

    # ── Dates ───────────────────────────────────────────────────────────────
    transaction_date: date
    authorized_date: date | None = None

    # ── Money ───────────────────────────────────────────────────────────────
    # Decimal, never float. Binary floats cannot represent 0.10 exactly and
    # financial sums must be exact.
    amount: Decimal = Decimal("0.00")
    iso_currency_code: str = "USD"

    # ── Source description, verbatim ────────────────────────────────────────
    description: str = ""
    merchant_name: str | None = None
    merchant_entity_id: str | None = None

    # ── Plaid classification, kept separate from ours ───────────────────────
    plaid_category_primary: str | None = None
    plaid_category_detailed: str | None = None
    plaid_category_confidence: str | None = None
    payment_channel: str | None = None
    transaction_code: str | None = None

    # ── Lifecycle ───────────────────────────────────────────────────────────
    is_pending: bool = False
    status: TransactionStatus = TransactionStatus.POSTED
    # Set on a POSTED transaction that supersedes an earlier PENDING one. The
    # pipeline tombstones the referenced pending row instead of leaving a
    # duplicate behind.
    pending_transaction_id: str | None = None

    # ── Ledgerly enrichment (recomputable) ──────────────────────────────────
    normalized_merchant: str | None = None
    category: str | None = None
    subcategory: str | None = None
    transaction_type: TransactionType = TransactionType.UNKNOWN
    is_transfer: bool = False
    transfer_group_id: str | None = None
    is_recurring: bool = False

    # ── User overrides ──────────────────────────────────────────────────────
    # When set, enrichment must not overwrite the corresponding field on
    # reprocess. This is what makes "rebuild everything from raw" safe.
    user_category_override: bool = False
    user_type_override: bool = False
    user_note: str | None = None

    # ── Lineage ─────────────────────────────────────────────────────────────
    ingested_at: datetime | None = None
    processed_at: datetime | None = None
    source_key: str | None = None
    sync_cursor: str | None = None

    # ── Derived helpers ─────────────────────────────────────────────────────

    @property
    def is_outflow(self) -> bool:
        """Money left the account."""
        return self.amount < 0

    @property
    def is_inflow(self) -> bool:
        """Money entered the account."""
        return self.amount > 0

    @property
    def abs_amount(self) -> Decimal:
        return abs(self.amount)

    @property
    def counts_as_spending(self) -> bool:
        """Whether this reduces net worth as *spending*.

        The single guard against double-counting: a transfer never counts, no
        matter which direction it moves or which account it touches.
        """
        return (
            self.transaction_type is TransactionType.EXPENSE
            and self.status is not TransactionStatus.REMOVED
        )

    @property
    def counts_as_income(self) -> bool:
        return (
            self.transaction_type is TransactionType.INCOME
            and self.status is not TransactionStatus.REMOVED
        )

    def __post_init__(self) -> None:
        # Guard against float creeping in from JSON parsing — a float amount is
        # a correctness bug, not a style issue, so fail loudly at construction.
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"amount must be Decimal, got {type(self.amount).__name__}. "
                "Parse money with Decimal(str(value)), never float()."
            )
        # is_transfer and transaction_type must agree; a divergence here would
        # silently corrupt every spending report.
        if self.is_transfer and self.transaction_type is not TransactionType.TRANSFER:
            raise ValueError(
                f"is_transfer=True but transaction_type={self.transaction_type}. "
                "These must agree."
            )

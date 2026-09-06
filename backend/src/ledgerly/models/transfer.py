"""Transfer groups — the matched pairs.

Mirrors `data/schemas/finance_transfer_groups.sql`.

A transfer is a *relationship between two transactions*, not a label on one.
Modelling it as a pair is what lets us prove both legs cancel and lets the UI
draw the link (DESIGN.md §3.7A). It is the product's core differentiator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class TransferKind(StrEnum):
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"  # checking -> savings
    # checking -> card. The expense already happened at purchase time, so the
    # payment must never be counted as spending (SPEC §18).
    CREDIT_CARD_PAYMENT = "CREDIT_CARD_PAYMENT"
    LOAN_PAYMENT = "LOAN_PAYMENT"
    UNKNOWN = "UNKNOWN"


class TransferStatus(StrEnum):
    CONFIRMED = "CONFIRMED"  # trusted: auto-matched above threshold, or user-confirmed
    SUGGESTED = "SUGGESTED"  # candidate awaiting user confirm/reject
    REJECTED = "REJECTED"  # user said no — kept so we never re-suggest this pair


class MatchMethod(StrEnum):
    AUTO_EXACT = "AUTO_EXACT"  # same day, exact opposite amounts
    AUTO_FUZZY = "AUTO_FUZZY"  # within date window, scored
    USER_MANUAL = "USER_MANUAL"
    RULE = "RULE"


@dataclass(slots=True)
class TransferGroup:
    transfer_group_id: str

    # Source = account money LEFT (its transaction amount is negative).
    # Destination = account money ENTERED (amount positive).
    source_transaction_id: str
    source_account_id: str
    destination_transaction_id: str
    destination_account_id: str

    amount: Decimal  # absolute value of the movement, always positive
    source_date: date
    destination_date: date

    transfer_kind: TransferKind = TransferKind.UNKNOWN
    status: TransferStatus = TransferStatus.SUGGESTED
    confidence: Decimal = Decimal("0.0")
    match_method: MatchMethod = MatchMethod.AUTO_FUZZY
    iso_currency_code: str = "USD"

    matched_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None

    @property
    def date_gap_days(self) -> int:
        """Days between the two legs. Cross-institution transfers commonly
        settle 1-3 days apart; same-day is the typical intra-bank case."""
        return abs((self.destination_date - self.source_date).days)

    @property
    def is_actionable(self) -> bool:
        """Whether this pair should suppress its legs from income/expense totals.

        Only CONFIRMED groups do. A SUGGESTED pair is still shown to the user as
        two ordinary transactions — we never silently remove money from the
        reports on a guess.
        """
        return self.status is TransferStatus.CONFIRMED

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(f"amount must be Decimal, got {type(self.amount).__name__}")
        if self.amount <= 0:
            raise ValueError(f"amount must be positive (absolute value), got {self.amount}")
        if self.source_account_id == self.destination_account_id:
            raise ValueError(
                "source and destination accounts must differ — a transfer moves money "
                "between two accounts"
            )

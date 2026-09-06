"""Accounts and their balances.

Mirrors `data/schemas/finance_accounts_snapshot.sql`. Live account state lives in
DynamoDB (operational); the daily snapshot lands in Iceberg (analytical).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class AccountType(StrEnum):
    """Plaid's top-level account types."""

    DEPOSITORY = "depository"  # checking, savings — asset
    CREDIT = "credit"  # credit card — liability
    LOAN = "loan"  # mortgage, student, auto — liability
    INVESTMENT = "investment"  # brokerage, retirement — asset
    OTHER = "other"


# Which types represent money owed rather than money held. Net worth keys off
# this, never off the sign of the balance — a credit card with $1,500 owed
# reports current_balance = +1500, a positive number that is a liability.
LIABILITY_TYPES: frozenset[AccountType] = frozenset(
    {AccountType.CREDIT, AccountType.LOAN}
)


@dataclass(slots=True)
class Account:
    account_id: str
    item_id: str

    institution_id: str | None = None
    institution_name: str | None = None

    name: str = ""
    official_name: str | None = None
    mask: str | None = None  # last 4 only — never store the full number
    account_type: AccountType = AccountType.OTHER
    account_subtype: str | None = None

    current_balance: Decimal | None = None
    available_balance: Decimal | None = None
    credit_limit: Decimal | None = None
    iso_currency_code: str = "USD"

    last_synced_at: datetime | None = None
    is_active: bool = True

    @property
    def is_liability(self) -> bool:
        return self.account_type in LIABILITY_TYPES

    @property
    def net_worth_contribution(self) -> Decimal:
        """Signed contribution to net worth.

        Assets add, liabilities subtract. Returns zero rather than guessing when
        the balance is unknown — a missing balance must not silently read as $0
        of debt.
        """
        if self.current_balance is None:
            return Decimal("0.00")
        if self.is_liability:
            return -abs(self.current_balance)
        return self.current_balance

    def __post_init__(self) -> None:
        for name in ("current_balance", "available_balance", "credit_limit"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                raise TypeError(f"{name} must be Decimal or None, got {type(value).__name__}")


@dataclass(slots=True)
class AccountSnapshot:
    """One account's balance on one day. Append-only, never updated.

    Plaid reports only the *current* balance, so balance history cannot be
    reconstructed after the fact. A missed day is gone permanently — this is the
    one table in the platform that is not rebuildable from the raw layer.
    """

    snapshot_date: date
    account_id: str
    item_id: str
    current_balance: Decimal | None
    available_balance: Decimal | None
    credit_limit: Decimal | None
    is_liability: bool
    account_type: AccountType
    account_subtype: str | None = None
    institution_name: str | None = None
    account_name: str | None = None
    account_mask: str | None = None
    iso_currency_code: str = "USD"
    captured_at: datetime | None = None
    source_key: str | None = None

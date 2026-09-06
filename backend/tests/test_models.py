"""Model invariant tests.

These cover the rules that, if broken, silently corrupt financial reporting —
the class of bug that competing products actually ship. They are cheap and they
guard the product's core claim, so they exist before the pipeline does.
"""

from datetime import date
from decimal import Decimal

import pytest

from ledgerly.models import (
    Account,
    AccountType,
    Transaction,
    TransactionStatus,
    TransactionType,
    TransferGroup,
    TransferStatus,
)


def txn(**kw) -> Transaction:
    base = dict(
        transaction_id="t1",
        account_id="acc_checking",
        item_id="item_1",
        transaction_date=date(2026, 9, 1),
        amount=Decimal("-42.10"),
    )
    return Transaction(**{**base, **kw})


class TestAmountSignConvention:
    """Negative leaves the account, positive enters it — flipped from Plaid."""

    def test_negative_is_outflow(self):
        assert txn(amount=Decimal("-42.10")).is_outflow

    def test_positive_is_inflow(self):
        assert txn(amount=Decimal("7500.00")).is_inflow

    def test_abs_amount_is_always_positive(self):
        assert txn(amount=Decimal("-42.10")).abs_amount == Decimal("42.10")

    def test_float_amount_is_rejected(self):
        """A float amount is a correctness bug, not a style issue: 0.1+0.2!=0.3."""
        with pytest.raises(TypeError, match="must be Decimal"):
            txn(amount=-42.10)  # type: ignore[arg-type]


class TestTransfersAreNeverCounted:
    """The core claim of the product (SPEC §19, DESIGN.md §1)."""

    def test_transfer_is_not_spending(self):
        t = txn(amount=Decimal("-2000.00"), transaction_type=TransactionType.TRANSFER,
                is_transfer=True)
        assert not t.counts_as_spending

    def test_transfer_is_not_income(self):
        t = txn(amount=Decimal("2000.00"), transaction_type=TransactionType.TRANSFER,
                is_transfer=True)
        assert not t.counts_as_income

    def test_credit_card_payment_is_not_spending(self):
        """SPEC §18. The expense already happened at purchase time."""
        payment = txn(transaction_id="t_pay", amount=Decimal("-1500.00"),
                      transaction_type=TransactionType.TRANSFER, is_transfer=True)
        assert not payment.counts_as_spending

    def test_transfer_pair_nets_to_zero_in_spending(self):
        """The end-to-end guarantee: $7,500 in, $3,500 spent, $2,000 moved to
        savings. Net spending must be $3,500 — not $5,500."""
        ledger = [
            txn(transaction_id="salary", amount=Decimal("7500.00"),
                transaction_type=TransactionType.INCOME),
            txn(transaction_id="rent", amount=Decimal("-3500.00"),
                transaction_type=TransactionType.EXPENSE),
            txn(transaction_id="sav_out", amount=Decimal("-2000.00"),
                transaction_type=TransactionType.TRANSFER, is_transfer=True),
            txn(transaction_id="sav_in", account_id="acc_savings",
                amount=Decimal("2000.00"),
                transaction_type=TransactionType.TRANSFER, is_transfer=True),
        ]
        spending = sum(t.abs_amount for t in ledger if t.counts_as_spending)
        income = sum(t.abs_amount for t in ledger if t.counts_as_income)
        assert spending == Decimal("3500.00")
        assert income == Decimal("7500.00")

    def test_is_transfer_and_type_must_agree(self):
        """A divergence here would silently corrupt every spending report."""
        with pytest.raises(ValueError, match="must agree"):
            txn(is_transfer=True, transaction_type=TransactionType.EXPENSE)


class TestRemovedTransactions:
    def test_removed_is_excluded_from_spending(self):
        t = txn(transaction_type=TransactionType.EXPENSE, status=TransactionStatus.REMOVED)
        assert not t.counts_as_spending


class TestNetWorth:
    """Liability status comes from account TYPE, never the sign of the balance."""

    def test_credit_card_positive_balance_is_a_liability(self):
        card = Account(account_id="c", item_id="i", account_type=AccountType.CREDIT,
                       current_balance=Decimal("1500.00"))
        assert card.is_liability
        assert card.net_worth_contribution == Decimal("-1500.00")

    def test_depository_adds(self):
        chk = Account(account_id="d", item_id="i", account_type=AccountType.DEPOSITORY,
                      current_balance=Decimal("4000.00"))
        assert chk.net_worth_contribution == Decimal("4000.00")

    def test_net_worth_sums_correctly(self):
        accounts = [
            Account(account_id="d", item_id="i", account_type=AccountType.DEPOSITORY,
                    current_balance=Decimal("8432.19")),
            Account(account_id="s", item_id="i", account_type=AccountType.DEPOSITORY,
                    current_balance=Decimal("24150.00")),
            Account(account_id="b", item_id="i", account_type=AccountType.INVESTMENT,
                    current_balance=Decimal("67204.88")),
            Account(account_id="c", item_id="i", account_type=AccountType.CREDIT,
                    current_balance=Decimal("1847.32")),
            Account(account_id="l", item_id="i", account_type=AccountType.LOAN,
                    current_balance=Decimal("12400.00")),
        ]
        assert sum(a.net_worth_contribution for a in accounts) == Decimal("85539.75")

    def test_unknown_balance_contributes_zero_not_debt(self):
        """A missing balance must not silently read as $0 of debt."""
        a = Account(account_id="x", item_id="i", account_type=AccountType.CREDIT,
                    current_balance=None)
        assert a.net_worth_contribution == Decimal("0.00")


class TestTransferGroup:
    def group(self, **kw) -> TransferGroup:
        base = dict(
            transfer_group_id="g1",
            source_transaction_id="t_out", source_account_id="acc_checking",
            destination_transaction_id="t_in", destination_account_id="acc_savings",
            amount=Decimal("2000.00"),
            source_date=date(2026, 9, 1), destination_date=date(2026, 9, 3),
        )
        return TransferGroup(**{**base, **kw})

    def test_date_gap(self):
        assert self.group().date_gap_days == 2

    def test_suggested_does_not_suppress_totals(self):
        """We never silently remove money from reports on a guess."""
        assert not self.group(status=TransferStatus.SUGGESTED).is_actionable

    def test_confirmed_suppresses_totals(self):
        assert self.group(status=TransferStatus.CONFIRMED).is_actionable

    def test_amount_must_be_positive(self):
        with pytest.raises(ValueError, match="must be positive"):
            self.group(amount=Decimal("-2000.00"))

    def test_same_account_is_rejected(self):
        with pytest.raises(ValueError, match="must differ"):
            self.group(destination_account_id="acc_checking")

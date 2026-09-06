"""Transfer detection tests.

These encode the scenarios SPEC §17 and §18 describe verbatim, because getting
them wrong is the failure this product exists to prevent.
"""

from datetime import date
from decimal import Decimal

from ledgerly.models import (
    Account, AccountType, Transaction, TransactionStatus, TransactionType,
    TransferKind, TransferStatus,
)
from ledgerly.pipeline.transfers import (
    AUTO_CONFIRM_THRESHOLD, find_transfers, score_pair,
)


def txn(tid, account, amount, day, **kw):
    return Transaction(
        transaction_id=tid, account_id=account, item_id="i1",
        transaction_date=date(2026, 9, day), amount=Decimal(amount),
        transaction_type=TransactionType.EXPENSE if Decimal(amount) < 0
        else TransactionType.INCOME,
        **kw,
    )


CHECKING = Account(account_id="chk", item_id="i1", name="Checking",
                   account_type=AccountType.DEPOSITORY)
SAVINGS = Account(account_id="sav", item_id="i1", name="Savings",
                  account_type=AccountType.DEPOSITORY)
CARD = Account(account_id="card", item_id="i1", name="Card",
               account_type=AccountType.CREDIT)
LOAN = Account(account_id="loan", item_id="i1", name="Loan",
               account_type=AccountType.LOAN)
ACCOUNTS = {a.account_id: a for a in (CHECKING, SAVINGS, CARD, LOAN)}


class TestSpecScenarios:
    def test_checking_to_savings_is_one_transfer(self):
        """SPEC §17: -$2,000 checking / +$2,000 savings is a TRANSFER, not
        $2,000 of expense plus $2,000 of income."""
        groups = find_transfers(
            [txn("out", "chk", "-2000.00", 1, description="ONLINE TRANSFER TO SAVINGS"),
             txn("in", "sav", "2000.00", 1, description="TRANSFER FROM CHECKING")],
            ACCOUNTS,
        )
        assert len(groups) == 1
        g = groups[0]
        assert g.status is TransferStatus.CONFIRMED
        assert g.transfer_kind is TransferKind.INTERNAL_TRANSFER
        assert g.amount == Decimal("2000.00")

    def test_credit_card_payment_is_a_transfer_not_spending(self):
        """SPEC §18: the expense already happened at purchase time."""
        groups = find_transfers(
            [txn("out", "chk", "-1500.00", 4, description="CHASE CREDIT CRD AUTOPAY"),
             txn("in", "card", "1500.00", 4, description="PAYMENT THANK YOU")],
            ACCOUNTS,
        )
        assert len(groups) == 1
        assert groups[0].transfer_kind is TransferKind.CREDIT_CARD_PAYMENT
        assert groups[0].status is TransferStatus.CONFIRMED

    def test_loan_payment_classified(self):
        groups = find_transfers(
            [txn("out", "chk", "-450.00", 3, description="STUDENT LOAN PAYMENT"),
             txn("in", "loan", "450.00", 3)],
            ACCOUNTS,
        )
        assert groups[0].transfer_kind is TransferKind.LOAN_PAYMENT

    def test_net_spending_excludes_transfers(self):
        """SPEC §19: income 7,500, real spending 3,500, transfer 2,000.
        Net spending must be 3,500 — not 5,500."""
        ledger = [
            txn("salary", "chk", "7500.00", 1),
            txn("rent", "chk", "-3500.00", 2),
            txn("xfer_out", "chk", "-2000.00", 3, description="TRANSFER TO SAVINGS"),
            txn("xfer_in", "sav", "2000.00", 3, description="TRANSFER FROM CHECKING"),
        ]
        groups = find_transfers(ledger, ACCOUNTS)
        paired = {g.source_transaction_id for g in groups} | {
            g.destination_transaction_id for g in groups
        }
        spending = sum(
            t.abs_amount for t in ledger
            if t.amount < 0 and t.transaction_id not in paired
        )
        assert spending == Decimal("3500.00")


class TestDisqualifiers:
    def test_same_account_never_pairs(self):
        assert score_pair(txn("a", "chk", "-100", 1), txn("b", "chk", "100", 1)) == 0

    def test_mismatched_amounts_never_pair(self):
        assert score_pair(txn("a", "chk", "-100.00", 1),
                          txn("b", "sav", "100.02", 1)) == 0

    def test_outside_date_window_never_pairs(self):
        assert score_pair(txn("a", "chk", "-100", 1), txn("b", "sav", "100", 20)) == 0

    def test_two_outflows_never_pair(self):
        assert score_pair(txn("a", "chk", "-100", 1), txn("b", "sav", "-100", 1)) == 0

    def test_different_currency_never_pairs(self):
        a = txn("a", "chk", "-100", 1)
        b = txn("b", "sav", "100", 1, iso_currency_code="EUR")
        assert score_pair(a, b) == 0

    def test_removed_transactions_are_ignored(self):
        groups = find_transfers(
            [txn("out", "chk", "-500", 1, status=TransactionStatus.REMOVED),
             txn("in", "sav", "500", 1)],
            ACCOUNTS,
        )
        assert groups == []


class TestGreedyAssignment:
    def test_a_transaction_belongs_to_at_most_one_group(self):
        """Three identical $500 movements must not cross-match into nine pairs."""
        ledger = [
            txn("o1", "chk", "-500.00", 1, description="TRANSFER"),
            txn("o2", "chk", "-500.00", 2, description="TRANSFER"),
            txn("i1", "sav", "500.00", 1, description="TRANSFER"),
            txn("i2", "sav", "500.00", 2, description="TRANSFER"),
        ]
        groups = find_transfers(ledger, ACCOUNTS)
        assert len(groups) == 2
        used = [g.source_transaction_id for g in groups] + [
            g.destination_transaction_id for g in groups
        ]
        assert len(used) == len(set(used)), "a transaction was claimed twice"

    def test_deterministic_group_ids(self):
        """Re-running detection must produce identical ids so the Iceberg MERGE
        stays idempotent."""
        ledger = [txn("out", "chk", "-100", 1, description="TRANSFER"),
                  txn("in", "sav", "100", 1, description="TRANSFER")]
        first = find_transfers(ledger, ACCOUNTS)
        second = find_transfers(ledger, ACCOUNTS)
        assert first[0].transfer_group_id == second[0].transfer_group_id


class TestConfidence:
    def test_weak_pair_is_suggested_not_confirmed(self):
        """Two unrelated same-amount transactions days apart with nothing
        transfer-like about them should not be auto-confirmed."""
        groups = find_transfers(
            [txn("out", "chk", "-20.00", 1, description="COFFEE SHOP"),
             txn("in", "sav", "20.00", 5, description="REFUND")],
            ACCOUNTS,
        )
        if groups:
            assert groups[0].status is TransferStatus.SUGGESTED
            assert groups[0].confidence < AUTO_CONFIRM_THRESHOLD

    def test_plaid_category_alone_cannot_confirm(self):
        """ADR 0005: Plaid labelled interest income TRANSFER_IN. The category
        must not be sufficient on its own."""
        score = score_pair(
            txn("a", "chk", "-4.22", 1, plaid_category_primary="TRANSFER_OUT",
                description="INTRST PYMNT"),
            txn("b", "sav", "4.22", 4, plaid_category_primary="TRANSFER_IN",
                description="INTRST PYMNT"),
        )
        # Reaches the suggestion band, but must stay under auto-confirm without
        # corroborating structural evidence.
        assert score < AUTO_CONFIRM_THRESHOLD

    def test_pair_sums_to_zero(self):
        """The checkable invariant a label can never provide."""
        ledger = [txn("out", "chk", "-2000.00", 1, description="TRANSFER"),
                  txn("in", "sav", "2000.00", 1, description="TRANSFER")]
        groups = find_transfers(ledger, ACCOUNTS)
        by_id = {t.transaction_id: t for t in ledger}
        g = groups[0]
        total = by_id[g.source_transaction_id].amount + by_id[g.destination_transaction_id].amount
        assert total == Decimal("0")

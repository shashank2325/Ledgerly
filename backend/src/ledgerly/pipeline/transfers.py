"""Transfer detection — pairing two transactions into one movement (SPEC §17).

This is the product's core differentiator. Competing apps store a transfer as a
category LABEL on a single transaction, which is why they double-count credit
card payments; Monarch's own documentation concedes the problem. A transfer is
a RELATIONSHIP between two transactions, so we only call something a transfer
when we have found both legs (ADR 0005).

The output is deliberately checkable: a matched pair must sum to zero. That
invariant is testable, and a label on one transaction never can be.

Pure functions — no AWS, no network — so the whole matcher can be tested
offline and safely re-run over history.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ledgerly.models import (
    Account,
    AccountType,
    MatchMethod,
    Transaction,
    TransactionStatus,
    TransferGroup,
    TransferKind,
    TransferStatus,
)

logger = logging.getLogger(__name__)

# How far apart the two legs may settle. Same-day is typical within one bank;
# cross-institution ACH routinely takes 1-3 days. Beyond 5 days the false-match
# rate rises faster than the recall gain.
MAX_DATE_GAP_DAYS = 5

# Amounts must match to the cent. Transfers move an exact figure — a tolerance
# here would pair a $50.00 transfer with an unrelated $50.02 purchase.
AMOUNT_TOLERANCE = Decimal("0.00")

# Above this, pair automatically. Below, surface as a suggestion for the user to
# confirm — we never silently remove money from spending totals on a guess.
AUTO_CONFIRM_THRESHOLD = Decimal("0.90")
# Below this, do not even suggest; the noise would train the user to click
# "confirm" without reading.
MIN_SUGGEST_THRESHOLD = Decimal("0.55")

# Tokens that appear in genuine transfer descriptions. Used as a weak positive
# signal only — never as sufficient evidence on its own.
TRANSFER_TOKENS = (
    "transfer", "xfer", "payment", "autopay", "ach", "online banking",
    "withdrawal", "deposit", "epay", "bill pay", "web pmt",
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A possible pairing, before greedy assignment picks winners."""

    source: Transaction       # money left this account (amount < 0)
    destination: Transaction  # money entered this account (amount > 0)
    score: Decimal
    kind: TransferKind

    @property
    def date_gap(self) -> int:
        return abs((self.destination.transaction_date - self.source.transaction_date).days)


def _tokens_match(source: Transaction, destination: Transaction) -> bool:
    text = f"{source.description} {destination.description}".lower()
    return any(token in text for token in TRANSFER_TOKENS)


def classify_kind(
    source_account: Account | None, destination_account: Account | None
) -> TransferKind:
    """What sort of movement this is.

    The distinction matters beyond labelling: a credit-card payment must never
    count as spending, because the expense already happened at purchase time
    (SPEC §18). Money moving to a credit or loan account is paying down debt.
    """
    if destination_account is None or source_account is None:
        return TransferKind.UNKNOWN
    if destination_account.account_type is AccountType.CREDIT:
        return TransferKind.CREDIT_CARD_PAYMENT
    if destination_account.account_type is AccountType.LOAN:
        return TransferKind.LOAN_PAYMENT
    return TransferKind.INTERNAL_TRANSFER


def score_pair(
    source: Transaction,
    destination: Transaction,
    *,
    source_account: Account | None = None,
    destination_account: Account | None = None,
) -> Decimal:
    """Confidence that these two legs are the same movement of money.

    Weighted so that no single weak signal can carry a pair over the
    auto-confirm line by itself — in particular Plaid's own transfer category,
    which live data showed labelling interest income and payroll as transfers
    (ADR 0005).
    """
    # Structural requirements. Failing any of these is disqualifying, not a
    # score penalty.
    if source.account_id == destination.account_id:
        return Decimal("0")
    if source.amount >= 0 or destination.amount <= 0:
        return Decimal("0")
    if abs(source.amount + destination.amount) > AMOUNT_TOLERANCE:
        return Decimal("0")
    if source.iso_currency_code != destination.iso_currency_code:
        return Decimal("0")

    gap = abs((destination.transaction_date - source.transaction_date).days)
    if gap > MAX_DATE_GAP_DAYS:
        return Decimal("0")

    # Exact opposite amounts across two different accounts is already strong
    # evidence; the remaining signals distinguish a real transfer from a
    # coincidence (two unrelated $20 transactions on the same day).
    score = Decimal("0.60")

    # Date proximity: same day is the common case for intra-bank movement.
    score += {0: Decimal("0.22"), 1: Decimal("0.17"), 2: Decimal("0.12")}.get(
        gap, Decimal("0.06")
    )

    # A destination that is a credit card or loan is highly indicative — nobody
    # receives income into a credit card.
    kind = classify_kind(source_account, destination_account)
    if kind in (TransferKind.CREDIT_CARD_PAYMENT, TransferKind.LOAN_PAYMENT):
        score += Decimal("0.14")

    # Plaid's explicit transfer marker on the raw record.
    if "transfer" in ((source.transaction_code or "") + (destination.transaction_code or "")).lower():
        score += Decimal("0.08")

    # Description language. Weighted meaningfully: "ONLINE TRANSFER TO SAVINGS"
    # paired with "TRANSFER FROM CHECKING" is corroborating evidence of the
    # movement itself, unlike Plaid's category which describes only one side.
    if _tokens_match(source, destination):
        score += Decimal("0.10")

    # Plaid's category, weighted low on purpose (ADR 0005).
    categories = f"{source.plaid_category_primary or ''} {destination.plaid_category_primary or ''}"
    if "TRANSFER" in categories.upper():
        score += Decimal("0.04")

    # Ordering sanity: money should leave on or before it arrives. A
    # destination dated before its source is possible (posting quirks) but less
    # likely, so it loses a little confidence rather than being disqualified.
    if destination.transaction_date < source.transaction_date:
        score -= Decimal("0.08")

    return min(score, Decimal("1.0"))


def find_transfers(
    transactions: list[Transaction],
    accounts: dict[str, Account] | None = None,
    *,
    now: datetime | None = None,
) -> list[TransferGroup]:
    """Pair transactions into transfer groups.

    Greedy assignment by descending score: the strongest evidence claims its
    legs first, and each transaction can belong to at most one group. Without
    that constraint, a recurring $500 transfer would cross-match against every
    other $500 transfer in the window and produce a combinatorial mess.
    """
    accounts = accounts or {}
    stamp = now or datetime.now()

    live = [
        t
        for t in transactions
        if t.status is not TransactionStatus.REMOVED and not t.is_transfer
    ]
    outflows = [t for t in live if t.amount < 0]
    inflows = [t for t in live if t.amount > 0]

    # Bucket inflows by absolute amount so each outflow only compares against
    # plausible partners instead of the whole set (O(n*k) rather than O(n^2)).
    by_amount: dict[Decimal, list[Transaction]] = {}
    for t in inflows:
        by_amount.setdefault(abs(t.amount), []).append(t)

    candidates: list[Candidate] = []
    for source in outflows:
        for destination in by_amount.get(abs(source.amount), ()):
            source_account = accounts.get(source.account_id)
            destination_account = accounts.get(destination.account_id)
            score = score_pair(
                source,
                destination,
                source_account=source_account,
                destination_account=destination_account,
            )
            if score >= MIN_SUGGEST_THRESHOLD:
                candidates.append(
                    Candidate(
                        source=source,
                        destination=destination,
                        score=score,
                        kind=classify_kind(source_account, destination_account),
                    )
                )

    # Highest score first; ties broken by the smaller date gap so the closer
    # pairing wins deterministically.
    candidates.sort(key=lambda c: (-c.score, c.date_gap))

    used: set[str] = set()
    groups: list[TransferGroup] = []

    for candidate in candidates:
        source_id = candidate.source.transaction_id
        destination_id = candidate.destination.transaction_id
        if source_id in used or destination_id in used:
            continue
        used.add(source_id)
        used.add(destination_id)

        confirmed = candidate.score >= AUTO_CONFIRM_THRESHOLD
        groups.append(
            TransferGroup(
                # Deterministic id derived from the two transaction ids, so
                # re-running detection over the same data yields the same group
                # id and the MERGE is idempotent.
                transfer_group_id=str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}|{destination_id}")
                ),
                source_transaction_id=source_id,
                source_account_id=candidate.source.account_id,
                destination_transaction_id=destination_id,
                destination_account_id=candidate.destination.account_id,
                amount=abs(candidate.source.amount),
                source_date=candidate.source.transaction_date,
                destination_date=candidate.destination.transaction_date,
                transfer_kind=candidate.kind,
                status=TransferStatus.CONFIRMED if confirmed else TransferStatus.SUGGESTED,
                confidence=candidate.score,
                match_method=MatchMethod.AUTO_EXACT
                if candidate.date_gap == 0
                else MatchMethod.AUTO_FUZZY,
                iso_currency_code=candidate.source.iso_currency_code,
                matched_at=stamp,
                confirmed_at=stamp if confirmed else None,
                confirmed_by="system" if confirmed else None,
            )
        )

    logger.info(
        "transfer_detection candidates=%d groups=%d confirmed=%d",
        len(candidates),
        len(groups),
        sum(1 for g in groups if g.status is TransferStatus.CONFIRMED),
    )
    return groups

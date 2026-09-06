"""Plaid transaction payload -> normalized Transaction (SPEC §16).

Pure function. No AWS, no network — so it can be re-run over stored raw
payloads to rebuild the curated layer whenever rules change (SPEC §15).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from ledgerly.models import Transaction, TransactionStatus, TransactionType


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _money(value: Any) -> Decimal:
    """Parse an amount without passing through float.

    Plaid sends a JSON number, already a float by the time Python sees it, so
    round-trip via str() to recover the exact decimal: Decimal(0.1) is
    0.1000000000000000055511151231, Decimal(str(0.1)) is exactly 0.1.
    """
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))


# Plaid Personal Finance Category primaries that represent SPENDING. Money
# arriving in one of these is a refund of a purchase, not income — an airline
# credit is not a paycheck. Anything not listed (INCOME*, TRANSFER_IN,
# BANK_FEES, or a null category) falls through to INCOME, which is the
# conservative default: it never hides money that arrived.
SPENDING_PRIMARIES: frozenset[str] = frozenset({
    "FOOD_AND_DRINK",
    "GENERAL_MERCHANDISE",
    "GENERAL_SERVICES",
    "TRANSPORTATION",
    "TRAVEL",
    "RENT_AND_UTILITIES",
    "ENTERTAINMENT",
    "PERSONAL_CARE",
    "MEDICAL",
    "HOME_IMPROVEMENT",
    "GOVERNMENT_AND_NON_PROFIT",
})


def classify(amount: Decimal, raw: dict[str, Any]) -> TransactionType:
    """Initial income/expense classification.

    Deliberately does NOT assign TRANSFER. Plaid's TRANSFER_IN/TRANSFER_OUT
    categories are unreliable — live data labels interest income as TRANSFER_IN
    and payroll as TRANSFER_OUT (ADR 0005). A transaction only becomes TRANSFER
    in Phase 6, when a counterparty leg is actually matched.

    Sign convention is already normalized here: negative left the account.
    """
    category = (raw.get("personal_finance_category") or {}).get("primary") or ""

    if amount > 0:
        # Money in. Whether it is income or a refund is decided by the category
        # it arrived under, not by the sign alone.
        #
        # This matters: sandbox data contains six $500 "United Airlines"
        # credits categorised TRAVEL. Treating any inflow as income turned
        # $3,000 of refunds into $3,000 of salary AND left $3,000 of travel
        # spending standing, distorting both sides of the report.
        if category.startswith("INCOME"):
            return TransactionType.INCOME
        if category in SPENDING_PRIMARIES:
            return TransactionType.REFUND
        return TransactionType.INCOME
    if amount < 0:
        return TransactionType.EXPENSE
    return TransactionType.UNKNOWN


def normalize_transaction(
    raw: dict[str, Any],
    *,
    item_id: str,
    sync_run_id: str | None = None,
    source_key: str | None = None,
    cursor: str | None = None,
    processed_at: datetime | None = None,
) -> Transaction:
    """Normalize one Plaid transaction."""
    now = processed_at or datetime.now(UTC)

    # ── THE SIGN FLIP ───────────────────────────────────────────────────────
    # Plaid: positive = money OUT of the account (an Uber charge is +6.33).
    # Ledgerly: negative = money LEFT the account.
    # Verified against live sandbox data 2026-09-06. This happens exactly once,
    # here; every downstream consumer sees only the normalized convention.
    amount = -_money(raw.get("amount"))

    is_pending = bool(raw.get("pending"))
    pfc = raw.get("personal_finance_category") or {}

    return Transaction(
        transaction_id=raw["transaction_id"],
        account_id=raw["account_id"],
        item_id=item_id,
        transaction_date=_to_date(raw.get("date")) or now.date(),
        authorized_date=_to_date(raw.get("authorized_date")),
        amount=amount,
        iso_currency_code=raw.get("iso_currency_code") or "USD",
        description=raw.get("name") or "",
        merchant_name=raw.get("merchant_name"),
        merchant_entity_id=raw.get("merchant_entity_id"),
        plaid_category_primary=pfc.get("primary"),
        plaid_category_detailed=pfc.get("detailed"),
        plaid_category_confidence=pfc.get("confidence_level"),
        payment_channel=raw.get("payment_channel"),
        transaction_code=raw.get("transaction_code"),
        is_pending=is_pending,
        status=TransactionStatus.PENDING if is_pending else TransactionStatus.POSTED,
        # The link from a posted transaction back to the pending one it
        # replaces. Without honouring this, every pending charge would leave a
        # duplicate behind once it posts.
        pending_transaction_id=raw.get("pending_transaction_id"),
        normalized_merchant=raw.get("merchant_name") or None,
        category=pfc.get("primary"),
        subcategory=pfc.get("detailed"),
        transaction_type=classify(amount, raw),
        is_transfer=False,
        transfer_group_id=None,
        ingested_at=now,
        processed_at=now,
        source_key=source_key,
        sync_cursor=cursor,
    )


def normalize_batch(
    raws: list[dict[str, Any]], **kwargs: Any
) -> tuple[list[Transaction], list[dict[str, Any]]]:
    """Normalize a page. Returns (transactions, failures).

    A single malformed transaction must not abort the whole batch — the rest is
    still valid data, and the failure is surfaced for inspection rather than
    swallowed.
    """
    ok: list[Transaction] = []
    failed: list[dict[str, Any]] = []
    for raw in raws:
        try:
            ok.append(normalize_transaction(raw, **kwargs))
        except Exception as exc:
            failed.append(
                {"transaction_id": raw.get("transaction_id"), "error": str(exc)}
            )
    return ok, failed

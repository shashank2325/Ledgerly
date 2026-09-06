"""Plaid account payload -> our Account model.

Pure function: no AWS, no network. Everything it needs is passed in, so it is
trivially testable and safe to re-run over stored raw payloads.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ledgerly.models import Account, AccountType


def _money(value: Any) -> Decimal | None:
    """Parse a balance without ever passing through float.

    Plaid sends JSON numbers, which Python has already parsed as float by the
    time we see them — so we round-trip through str() to recover the exact
    decimal representation. `Decimal(0.1)` is 0.1000000000000000055511151231;
    `Decimal(str(0.1))` is exactly 0.1.

    Investment balances carry up to 4 decimal places (a sandbox 401k reports
    23631.9805), which is why the balance columns are decimal(19,4) and not
    (16,2) — see data/schemas/finance_accounts_snapshot.sql.
    """
    if value is None:
        return None
    return Decimal(str(value))


def normalize_accounts(
    plaid_accounts: list[dict[str, Any]],
    *,
    item_id: str,
    institution_id: str | None = None,
    institution_name: str | None = None,
    synced_at: datetime | None = None,
) -> list[Account]:
    """Normalize a `/accounts/get` response.

    Unknown account types degrade to OTHER rather than raising: Plaid can add
    types, and a new type must not break ingestion for every other account.
    """
    synced = synced_at or datetime.now(UTC)
    accounts: list[Account] = []

    for raw in plaid_accounts:
        balances = raw.get("balances") or {}

        try:
            account_type = AccountType(raw.get("type", "other"))
        except ValueError:
            account_type = AccountType.OTHER

        accounts.append(
            Account(
                account_id=raw["account_id"],
                item_id=item_id,
                institution_id=institution_id,
                institution_name=institution_name,
                name=raw.get("name", ""),
                official_name=raw.get("official_name"),
                # Last 4 only. Plaid never sends the full number, and we would
                # not store it if it did (SPEC §32).
                mask=raw.get("mask"),
                account_type=account_type,
                account_subtype=raw.get("subtype"),
                current_balance=_money(balances.get("current")),
                available_balance=_money(balances.get("available")),
                credit_limit=_money(balances.get("limit")),
                iso_currency_code=balances.get("iso_currency_code") or "USD",
                last_synced_at=synced,
                is_active=True,
            )
        )

    return accounts

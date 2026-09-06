"""DynamoDB repositories for operational state (SPEC §10).

The items table holds Plaid access tokens. Only the Plaid Lambda's IAM role can
reach it; the API Lambda is denied outright (ADR 0004). Nothing in this module
may log a token or return one in a structure bound for an HTTP response.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from ledgerly.models import Account, AccountType

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class PlaidItem:
    """A connected institution.

    `access_token` is present in memory and at rest but must never be
    serialized into a response, a log line, or S3.
    """

    item_id: str
    access_token: str
    institution_id: str | None = None
    institution_name: str | None = None
    sync_cursor: str | None = None
    last_synced_at: str | None = None
    status: str = "ACTIVE"  # ACTIVE | LOGIN_REQUIRED | REMOVED
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_public_dict(self) -> dict[str, Any]:
        """Response-safe projection. Deliberately constructed by allow-list, not
        by deleting the token from a full dict — a new secret field added later
        must not leak by default."""
        return {
            "item_id": self.item_id,
            "institution_id": self.institution_id,
            "institution_name": self.institution_name,
            "status": self.status,
            "last_synced_at": self.last_synced_at,
            "created_at": self.created_at,
        }


class ItemRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def put(self, item: PlaidItem) -> None:
        item.updated_at = _now()
        self._table.put_item(Item=asdict(item))
        # item_id only — never the token.
        logger.info("item_saved item_id=%s status=%s", item.item_id, item.status)

    def get(self, item_id: str) -> PlaidItem | None:
        response = self._table.get_item(Key={"item_id": item_id})
        raw = response.get("Item")
        return PlaidItem(**raw) if raw else None

    def list_all(self) -> list[PlaidItem]:
        """Scan is correct here: the table holds one row per connected bank —
        single digits. A query pattern would be premature."""
        response = self._table.scan()
        return [PlaidItem(**raw) for raw in response.get("Items", [])]

    def find_active_by_institution(self, institution_id: str) -> PlaidItem | None:
        """Find an existing live connection to the same institution.

        Guards against the duplicate-connection bug: Plaid mints a NEW item_id
        every time Link completes, even for a bank already connected, and the
        accounts under it get NEW account_ids. Two links of one bank therefore
        produce two copies of every account — and net worth silently doubles.
        """
        for item in self.list_all():
            if item.institution_id == institution_id and item.status != "REMOVED":
                return item
        return None

    def update_cursor(self, item_id: str, cursor: str) -> None:
        """Persist the sync cursor. This is the idempotency anchor for
        `/transactions/sync` (SPEC §12) — it must be written only after the
        corresponding data is durably stored."""
        self._table.update_item(
            Key={"item_id": item_id},
            UpdateExpression="SET sync_cursor = :c, last_synced_at = :t, updated_at = :t",
            ExpressionAttributeValues={":c": cursor, ":t": _now()},
        )

    def mark_status(self, item_id: str, status: str) -> None:
        self._table.update_item(
            Key={"item_id": item_id},
            UpdateExpression="SET #s = :s, updated_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status, ":t": _now()},
        )


class AccountRepository:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def put_many(self, accounts: list[Account]) -> None:
        with self._table.batch_writer() as batch:
            for account in accounts:
                batch.put_item(Item=self._serialize(account))
        logger.info("accounts_saved count=%d", len(accounts))

    def list_by_item(self, item_id: str) -> list[Account]:
        response = self._table.query(
            IndexName="item_id-index",
            KeyConditionExpression=Key("item_id").eq(item_id),
        )
        return [self._deserialize(raw) for raw in response.get("Items", [])]

    def list_all(self) -> list[Account]:
        response = self._table.scan()
        return [self._deserialize(raw) for raw in response.get("Items", [])]

    @staticmethod
    def _serialize(account: Account) -> dict[str, Any]:
        # DynamoDB stores numbers as Decimal natively — money is never converted
        # through float on the way in or out.
        return {
            "account_id": account.account_id,
            "item_id": account.item_id,
            "institution_id": account.institution_id,
            "institution_name": account.institution_name,
            "name": account.name,
            "official_name": account.official_name,
            "mask": account.mask,
            "account_type": str(account.account_type),
            "account_subtype": account.account_subtype,
            "current_balance": account.current_balance,
            "available_balance": account.available_balance,
            "credit_limit": account.credit_limit,
            "iso_currency_code": account.iso_currency_code,
            "last_synced_at": account.last_synced_at.isoformat()
            if account.last_synced_at
            else None,
            "is_active": account.is_active,
            "updated_at": _now(),
        }

    @staticmethod
    def _deserialize(raw: dict[str, Any]) -> Account:
        def money(key: str) -> Decimal | None:
            value = raw.get(key)
            return Decimal(str(value)) if value is not None else None

        synced = raw.get("last_synced_at")
        return Account(
            account_id=raw["account_id"],
            item_id=raw["item_id"],
            institution_id=raw.get("institution_id"),
            institution_name=raw.get("institution_name"),
            name=raw.get("name", ""),
            official_name=raw.get("official_name"),
            mask=raw.get("mask"),
            account_type=AccountType(raw.get("account_type", "other")),
            account_subtype=raw.get("account_subtype"),
            current_balance=money("current_balance"),
            available_balance=money("available_balance"),
            credit_limit=money("credit_limit"),
            iso_currency_code=raw.get("iso_currency_code", "USD"),
            last_synced_at=datetime.fromisoformat(synced) if synced else None,
            is_active=raw.get("is_active", True),
        )

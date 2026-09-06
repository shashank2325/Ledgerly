"""Sync orchestration — Plaid -> raw S3 -> normalized -> Iceberg (SPEC §12).

The ordering in `run_sync` is the correctness-critical part of this system:

  1. fetch a page from Plaid
  2. write it to the raw layer  ......... durable, immutable, replayable
  3. normalize
  4. upsert into Iceberg
  5. apply supersessions and removals
  6. ONLY THEN advance the stored cursor

The cursor is the pipeline's memory. Advancing it before the data is durable
would permanently skip transactions — Plaid will never send them again. Every
step before it is idempotent, so a crash anywhere replays harmlessly.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from ledgerly.analytics import AthenaClient, IcebergWriter
from ledgerly.pipeline.accounts import normalize_accounts
from ledgerly.pipeline.transactions import normalize_batch
from ledgerly.plaid import PlaidClient, PlaidError
from ledgerly.storage.raw import RawWriter
from ledgerly.storage.repositories import AccountRepository, ItemRepository, PlaidItem

logger = logging.getLogger(__name__)

# Plaid caps /transactions/sync at 500 per page.
PAGE_SIZE = 500
# Defensive bound: a cursor bug that never reports has_more=false would
# otherwise loop until the Lambda times out.
MAX_PAGES = 50


@dataclass
class SyncResult:
    item_id: str
    sync_run_id: str
    added: int = 0
    modified: int = 0
    removed: int = 0
    superseded: int = 0
    pages: int = 0
    accounts_refreshed: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)
    initial_load: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "sync_run_id": self.sync_run_id,
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "superseded": self.superseded,
            "pages": self.pages,
            "accounts_refreshed": self.accounts_refreshed,
            "initial_load": self.initial_load,
            "failures": len(self.failures),
            "error": self.error,
        }


def run_sync(
    item: PlaidItem,
    *,
    plaid: PlaidClient,
    raw: RawWriter,
    athena: AthenaClient,
    database: str,
    items_repo: ItemRepository,
    accounts_repo: AccountRepository,
) -> SyncResult:
    sync_run_id = str(uuid.uuid4())
    result = SyncResult(
        item_id=item.item_id,
        sync_run_id=sync_run_id,
        initial_load=item.sync_cursor is None,
    )
    writer = IcebergWriter(athena, database)
    cursor = item.sync_cursor

    logger.info(
        "sync_start item_id=%s run=%s initial=%s",
        item.item_id, sync_run_id, result.initial_load,
    )

    try:
        for page in range(1, MAX_PAGES + 1):
            response = plaid.transactions_sync(
                item.access_token, cursor=cursor, count=PAGE_SIZE
            )

            # (2) Raw first, always. If anything below fails, the source data
            # is already safe and this run can simply be repeated.
            source_key = raw.write_transactions(
                response,
                item_id=item.item_id,
                sync_run_id=sync_run_id,
                page=page,
                request_cursor=cursor,
            )

            next_cursor = response.get("next_cursor")
            added = response.get("added", [])
            modified = response.get("modified", [])
            removed = [r["transaction_id"] for r in response.get("removed", [])]

            # (3) Normalize. `added` and `modified` are handled identically —
            # MERGE resolves which is which by transaction_id.
            transactions, failures = normalize_batch(
                added + modified,
                item_id=item.item_id,
                sync_run_id=sync_run_id,
                source_key=source_key,
                cursor=next_cursor,
            )
            result.failures.extend(failures)

            # (4) and (5)
            writer.upsert(transactions)
            result.superseded += writer.supersede_pending(transactions)
            result.removed += writer.remove(removed)

            result.added += len(added)
            result.modified += len(modified)
            result.pages = page

            cursor = next_cursor
            if not response.get("has_more"):
                break
        else:
            logger.warning("sync_page_limit item_id=%s pages=%d", item.item_id, MAX_PAGES)

        # Balances change with every sync and are cheap to refresh here.
        accounts_response = plaid.get_accounts(item.access_token)
        raw.write_accounts(
            accounts_response, item_id=item.item_id, sync_run_id=sync_run_id
        )
        accounts = normalize_accounts(
            accounts_response.get("accounts", []),
            item_id=item.item_id,
            institution_id=item.institution_id,
            institution_name=item.institution_name,
        )
        accounts_repo.put_many(accounts)
        result.accounts_refreshed = len(accounts)

        # (6) Last. Everything above is durable before the cursor moves.
        if cursor:
            items_repo.update_cursor(item.item_id, cursor)

        logger.info("sync_done %s", result.to_dict())

    except PlaidError as exc:
        result.error = exc.error_code or "plaid_error"
        # A re-auth requirement is a state change worth persisting so the UI can
        # prompt for a reconnect instead of silently failing forever.
        if exc.is_item_login_required:
            items_repo.mark_status(item.item_id, "LOGIN_REQUIRED")
        logger.error("sync_failed item_id=%s code=%s", item.item_id, exc.error_code)

    except Exception as exc:
        result.error = str(exc)[:200]
        logger.exception("sync_failed item_id=%s", item.item_id)

    return result


def record_run(table: Any, result: SyncResult) -> None:
    """Persist the run for the UI's 'last synced' and for debugging without
    trawling CloudWatch. TTL'd after 90 days by DynamoDB."""
    now = datetime.now(UTC)
    table.put_item(
        Item={
            "item_id": result.item_id,
            "started_at": now.isoformat(),
            "expires_at": int((now + timedelta(days=90)).timestamp()),
            **{k: v for k, v in result.to_dict().items() if v is not None},
        }
    )

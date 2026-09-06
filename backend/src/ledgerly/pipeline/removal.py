"""Disconnecting an institution and removing its data.

Removal spans four stores, and the ORDER matters. Plaid is disconnected first:
if a later step fails, the worst outcome is orphaned local data with no live
connection, which is repairable. The reverse order could leave a connection
alive that the user believes is gone — and in production, still being billed.

The raw layer is deliberately NOT deleted. It is immutable by design (SPEC §15)
and is what makes the curated layer rebuildable. Deleting it would mean an
accidental disconnect is unrecoverable. It is inert once the item is gone —
nothing queries it — and can be purged separately if genuinely required.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3

from ledgerly.analytics import AthenaClient
from ledgerly.analytics.iceberg import sql_literal
from ledgerly.plaid import PlaidClient, PlaidError
from ledgerly.storage.repositories import ItemRepository

logger = logging.getLogger(__name__)


def remove_item(
    item_id: str,
    *,
    plaid: PlaidClient,
    items_repo: ItemRepository,
    accounts_table: str,
    athena: AthenaClient,
    database: str,
) -> dict[str, Any]:
    item = items_repo.get(item_id)
    if item is None:
        return {"error": "item_not_found", "item_id": item_id}

    result: dict[str, Any] = {
        "item_id": item_id,
        "institution_name": item.institution_name,
        "plaid_disconnected": False,
        "accounts_removed": 0,
        "transactions_removed": 0,
        "transfer_groups_removed": 0,
        "raw_retained": True,
    }

    # 1. Stop the connection at Plaid, so nothing new can arrive mid-removal.
    try:
        plaid.remove_item(item.access_token)
        result["plaid_disconnected"] = True
    except PlaidError as exc:
        # An already-invalid item is fine — the goal state is "not connected".
        logger.warning("plaid_remove_failed item_id=%s code=%s", item_id, exc.error_code)
        result["plaid_error"] = exc.error_code

    # 2. Account rows, and the ids needed to scope the analytical deletes.
    dynamo = boto3.resource("dynamodb")
    accounts = dynamo.Table(accounts_table)
    account_ids: list[str] = []
    response = accounts.query(
        IndexName="item_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("item_id").eq(item_id),
    )
    with accounts.batch_writer() as batch:
        for row in response.get("Items", []):
            account_ids.append(row["account_id"])
            batch.delete_item(Key={"account_id": row["account_id"]})
    result["accounts_removed"] = len(account_ids)

    # 3. Curated transactions. A hard DELETE, not a tombstone: the user asked
    # for the account's data to be gone, and a tombstoned row would still
    # surface in "removed" views and keep its merchant strings queryable.
    deleted = athena.query(
        f"SELECT count(*) AS n FROM {database}.transactions "
        f"WHERE item_id = {sql_literal(item_id)}"
    )
    result["transactions_removed"] = int(deleted[0]["n"]) if deleted else 0
    if result["transactions_removed"]:
        athena.execute(
            f"DELETE FROM {database}.transactions WHERE item_id = {sql_literal(item_id)}"
        )

    # 4. Transfer groups with a leg in a removed account. Leaving these would
    # produce half a pair — a group referencing a transaction that no longer
    # exists, which the ledger cannot render and whose legs cannot be shown to
    # cancel.
    if account_ids:
        ids = ", ".join(sql_literal(a) for a in account_ids)
        groups = athena.query(
            f"SELECT count(*) AS n FROM {database}.transfer_groups "
            f"WHERE source_account_id IN ({ids}) OR destination_account_id IN ({ids})"
        )
        result["transfer_groups_removed"] = int(groups[0]["n"]) if groups else 0
        if result["transfer_groups_removed"]:
            athena.execute(
                f"DELETE FROM {database}.transfer_groups "
                f"WHERE source_account_id IN ({ids}) OR destination_account_id IN ({ids})"
            )

    # 5. Operational record last — while it exists, the removal is resumable.
    dynamo.Table(items_repo._table.name).delete_item(Key={"item_id": item_id})

    logger.info("item_removed %s", result)
    return result

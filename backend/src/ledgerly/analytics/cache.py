"""Read-through serving cache in DynamoDB.

SPEC §8 draws the line explicitly: Athena is for analytics, not for every
interactive read. The dashboard and report endpoints crossed it — each Athena
query against an Iceberg table costs ~1s of fixed overhead (Glue metadata plus
manifest resolution; a bare `SELECT 1` is 0.4s, `count(*)` on the table is
1.0s even scanning zero bytes), so a page issuing several took 3-5 seconds.

This is the serving layer the spec asked for. Athena still PRODUCES the
analytics; DynamoDB SERVES them. A hit is a single GetItem — tens of
milliseconds instead of seconds.

Correctness comes from the invalidation rule, which is simple because the data
only changes in one place: a sync. Writers call `invalidate()`; entries also
carry a TTL so a missed invalidation self-heals rather than serving a stale
number indefinitely.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any, TypeVar

import boto3

logger = logging.getLogger(__name__)

T = TypeVar("T")

# A cached answer is only wrong if a sync happened, and syncs invalidate
# explicitly. The TTL is the backstop for a missed invalidation, not the
# freshness mechanism — hence hours rather than seconds.
DEFAULT_TTL_SECONDS = 6 * 3600


def _table():
    import os

    name = os.environ.get("CACHE_TABLE", "")
    if not name:
        return None
    return boto3.resource("dynamodb").Table(name)


def cached(
    key: str,
    producer: Callable[[], T],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> T:
    """Return the cached payload for `key`, computing and storing it on a miss.

    The cache is best-effort in both directions: if DynamoDB is unavailable or
    unconfigured, this degrades to calling `producer` directly. A caching layer
    must never be the reason a page fails to load.
    """
    table = _table()

    if table is not None:
        try:
            item = table.get_item(Key={"cache_key": key}).get("Item")
            if item and int(item.get("expires_at", 0)) > time.time():
                logger.info("cache_hit key=%s", key)
                return json.loads(item["payload"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_read_failed key=%s: %s", key, exc)

    logger.info("cache_miss key=%s", key)
    value = producer()

    if table is not None:
        try:
            table.put_item(
                Item={
                    "cache_key": key,
                    # Stored as a JSON string, not a DynamoDB map: the payloads
                    # are nested and contain Decimals, and round-tripping
                    # through DynamoDB's type system would quietly change
                    # numeric representations. JSON keeps money as the exact
                    # strings the API already returns.
                    "payload": json.dumps(value, default=_json_default),
                    "expires_at": int(time.time()) + ttl_seconds,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_write_failed key=%s: %s", key, exc)

    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def invalidate() -> int:
    """Drop every entry. Called after a sync, a reprocess, or a removal — any
    point where the underlying analytics have moved."""
    table = _table()
    if table is None:
        return 0
    try:
        keys = [row["cache_key"] for row in table.scan(ProjectionExpression="cache_key").get("Items", [])]
        with table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key={"cache_key": key})
        logger.info("cache_invalidated count=%d", len(keys))
        return len(keys)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_invalidate_failed: %s", exc)
        return 0

"""Raw layer writer — immutable Plaid payloads in S3 (SPEC §15).

The raw write happens BEFORE any normalization and must succeed before the
pipeline continues. If normalization later crashes, the source data is already
durable and the run is replayable — that is the entire reason this layer exists.
"""

from __future__ import annotations

import gzip
import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class RawWriter:
    def __init__(self, bucket: str) -> None:
        self._s3 = boto3.client("s3")
        self._bucket = bucket

    def write_transactions(
        self,
        payload: dict[str, Any],
        *,
        item_id: str,
        sync_run_id: str,
        page: int,
        request_cursor: str | None,
    ) -> str:
        """Persist one page of a /transactions/sync response verbatim."""
        key = (
            f"raw/plaid/transactions/item_id={item_id}/"
            f"dt={datetime.now(UTC):%Y-%m-%d}/{sync_run_id}-p{page:03d}.json.gz"
        )
        return self._put(
            key,
            {
                "_meta": {
                    "sync_run_id": sync_run_id,
                    "item_id": item_id,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "plaid_endpoint": "/transactions/sync",
                    "request_cursor": request_cursor,
                    "response_cursor": payload.get("next_cursor"),
                    "has_more": payload.get("has_more", False),
                    "page": page,
                    "schema_version": SCHEMA_VERSION,
                },
                "payload": payload,
            },
        )

    def write_accounts(
        self, payload: dict[str, Any], *, item_id: str, sync_run_id: str
    ) -> str:
        key = (
            f"raw/plaid/accounts/item_id={item_id}/"
            f"dt={datetime.now(UTC):%Y-%m-%d}/{sync_run_id}.json.gz"
        )
        return self._put(
            key,
            {
                "_meta": {
                    "sync_run_id": sync_run_id,
                    "item_id": item_id,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "plaid_endpoint": "/accounts/get",
                    "schema_version": SCHEMA_VERSION,
                },
                "payload": payload,
            },
        )

    def _put(self, key: str, envelope: dict[str, Any]) -> str:
        # The envelope references the item by item_id only. An access token
        # must never be serialized into S3 (SPEC §32) — the Plaid response
        # bodies we store do not contain one, and nothing here adds it.
        body = gzip.compress(json.dumps(envelope, separators=(",", ":")).encode())
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
        )
        logger.info("raw_written key=%s bytes=%d", key, len(body))
        return key

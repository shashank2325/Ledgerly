"""Rebuild the curated layer from the immutable raw layer (SPEC §15).

This is the capability the whole architecture exists to provide. Every hosted
budgeting app makes you live with whatever it decided at ingest time; because
raw Plaid payloads are kept verbatim and forever, changing a classification rule
here can retroactively correct years of history.

Nothing is re-fetched from Plaid. The source is S3, so this costs no API calls,
works if an item has since been disconnected, and produces byte-identical input
every time it runs.
"""

from __future__ import annotations

import gzip
import json
import logging
from typing import Any

import boto3

from ledgerly.analytics import AthenaClient, IcebergWriter
from ledgerly.pipeline.transactions import normalize_batch

logger = logging.getLogger(__name__)

RAW_PREFIX = "raw/plaid/transactions/"


def reprocess_transactions(
    *,
    bucket: str,
    client: AthenaClient,
    database: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-normalize every stored raw payload and MERGE the result.

    Safe to run at any time: normalization is deterministic and the MERGE keys
    on transaction_id, so this corrects existing rows rather than duplicating
    them. User overrides are preserved by the MERGE itself — a manual category
    survives a rebuild, which is what makes reprocessing safe to offer.
    """
    s3 = boto3.client("s3")
    writer = IcebergWriter(client, database)

    objects: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=RAW_PREFIX):
        objects.extend(o["Key"] for o in page.get("Contents", []))

    total_read = 0
    total_written = 0
    failures: list[dict[str, Any]] = []

    for key in sorted(objects):
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        # Envelopes are gzipped; tolerate an uncompressed one rather than
        # aborting a rebuild over a single legacy object.
        try:
            envelope = json.loads(gzip.decompress(body))
        except (OSError, gzip.BadGzipFile):
            envelope = json.loads(body)

        meta = envelope.get("_meta", {})
        payload = envelope.get("payload", {})
        raw_transactions = payload.get("added", []) + payload.get("modified", [])
        if not raw_transactions:
            continue

        transactions, batch_failures = normalize_batch(
            raw_transactions,
            item_id=meta.get("item_id", ""),
            sync_run_id=meta.get("sync_run_id"),
            source_key=key,
            cursor=meta.get("response_cursor"),
        )
        failures.extend(batch_failures)
        total_read += len(raw_transactions)

        if not dry_run:
            total_written += writer.upsert(transactions)
            writer.supersede_pending(transactions)

    result = {
        "raw_objects": len(objects),
        "transactions_read": total_read,
        "transactions_written": total_written,
        "failures": len(failures),
        "dry_run": dry_run,
    }
    logger.info("reprocess_complete %s", result)
    return result

"""Sync Lambda: ingestion entrypoint.

Invoked three ways, all landing in the same code path:
  - HTTP  POST /sync            (manual trigger from the UI)
  - EventBridge scheduled       (periodic reconciliation, SPEC §13)
  - Plaid webhook               (Phase 4b)

Routes (mounted under /sync by API Gateway):
    POST /sync                -> sync every active item
    POST /sync/schemas        -> apply Iceberg DDL (idempotent bootstrap)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import boto3

from ledgerly.analytics import AthenaClient
from ledgerly.analytics.ddl import apply_schemas
from ledgerly.config import get_config
from ledgerly.pipeline.sync import record_run, run_sync
from ledgerly.plaid import PlaidClient
from ledgerly.storage import AccountRepository, ItemRepository, get_plaid_credentials
from ledgerly.storage.raw import RawWriter

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, separators=(",", ":"), default=str),
    }


def _athena() -> AthenaClient:
    cfg = get_config()
    return AthenaClient(workgroup=cfg.athena_workgroup, database=cfg.glue_database)


def sync_all() -> dict[str, Any]:
    """Sync every active item.

    One item failing must not stop the others — a bank requiring re-auth should
    not block a healthy connection from updating.
    """
    cfg = get_config()
    items_repo = ItemRepository(cfg.items_table)
    accounts_repo = AccountRepository(cfg.accounts_table)
    runs_table = boto3.resource("dynamodb").Table(cfg.sync_runs_table)

    plaid = PlaidClient(get_plaid_credentials(cfg.plaid_secret_arn))
    raw = RawWriter(cfg.data_bucket)
    athena = _athena()

    results = []
    for item in items_repo.list_all():
        if item.status == "REMOVED":
            continue
        result = run_sync(
            item,
            plaid=plaid,
            raw=raw,
            athena=athena,
            database=cfg.glue_database,
            items_repo=items_repo,
            accounts_repo=accounts_repo,
        )
        record_run(runs_table, result)
        results.append(result.to_dict())

    return {
        "items_synced": len(results),
        "results": results,
        "total_added": sum(r["added"] for r in results),
        "total_removed": sum(r["removed"] for r in results),
        "total_superseded": sum(r["superseded"] for r in results),
    }


def bootstrap_schemas() -> dict[str, Any]:
    """Create the Iceberg tables. Idempotent — safe to call repeatedly."""
    cfg = get_config()
    return {
        "database": cfg.glue_database,
        "schemas": apply_schemas(
            _athena(), data_bucket=cfg.data_bucket, database=cfg.glue_database
        ),
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "POST")
    path = http.get("path", "/sync")
    # EventBridge invokes with no requestContext; treat that as a full sync.
    scheduled = "requestContext" not in event

    try:
        if scheduled or (method == "POST" and path == "/sync"):
            body = sync_all()
        elif method == "POST" and path == "/sync/schemas":
            body = bootstrap_schemas()
        else:
            return _response(404, {"error": "not_found", "path": path})

        status = 200
    except ValueError as exc:
        # Empty credentials for the selected Plaid environment.
        logger.error("configuration_error: %s", exc)
        status, body = 503, {"error": "configuration_error", "detail": str(exc)}
    except Exception as exc:
        logger.exception("sync_handler_failed")
        status, body = 500, {"error": "internal_error", "detail": str(exc)[:200]}

    logger.info(
        json.dumps({"path": path, "scheduled": scheduled, "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
    )
    return _response(status, body)

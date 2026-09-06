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

JSON_HEADERS = {"content-type": "application/json"}


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": JSON_HEADERS,
        "body": json.dumps(body, separators=(",", ":"), default=str),
    }



def _bearer(event: dict[str, Any]) -> str | None:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    value = headers.get("authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def _require_session(event: dict[str, Any]) -> dict[str, Any] | None:
    """Return an error response if the request lacks a valid session, else None.

    Sync triggers Plaid calls and Athena queries, both of which cost money, so
    HTTP invocation is closed. EventBridge invocations bypass this by design —
    they carry no requestContext and are authenticated by IAM instead.
    """
    from ledgerly.auth import AuthError, verify_token

    token = _bearer(event)
    if not token:
        return {"statusCode": 401, "headers": JSON_HEADERS,
                "body": json.dumps({"error": "authentication_required"})}
    secret_arn = get_config().auth_secret_arn
    if not secret_arn:
        # Deployment problem, not a caller problem. Say so plainly rather than
        # letting boto3 raise an unhandled ParamValidationError as a 500.
        logger.error("auth_secret_arn_not_configured")
        return {"statusCode": 503, "headers": JSON_HEADERS,
                "body": json.dumps({"error": "auth_not_configured"})}
    try:
        verify_token(token, secret_arn=secret_arn)
    except AuthError:
        return {"statusCode": 401, "headers": JSON_HEADERS,
                "body": json.dumps({"error": "invalid_or_expired_token"})}
    return None


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

    detection = detect_transfers()

    return {
        "items_synced": len(results),
        "transfer_detection": detection,
        "results": results,
        "total_added": sum(r["added"] for r in results),
        "total_removed": sum(r["removed"] for r in results),
        "total_superseded": sum(r["superseded"] for r in results),
    }


def detect_transfers() -> dict[str, Any]:
    """Pair transactions into transfers and reclassify their legs (SPEC §17)."""
    from ledgerly.pipeline.detect import detect_and_persist

    cfg = get_config()
    accounts = AccountRepository(cfg.accounts_table).list_all()
    return detect_and_persist(_athena(), cfg.glue_database, accounts)


def reprocess() -> dict[str, Any]:
    """Rebuild the curated layer from raw S3, then re-run transfer detection.

    Detection must follow, because reclassification can change which
    transactions are eligible to pair.
    """
    from ledgerly.pipeline.reprocess import reprocess_transactions

    cfg = get_config()
    rebuilt = reprocess_transactions(
        bucket=cfg.data_bucket, client=_athena(), database=cfg.glue_database
    )
    return {"reprocess": rebuilt, "transfer_detection": detect_transfers()}


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

    # Scheduled invocations are authenticated by IAM, not a session token.
    if not scheduled:
        denied = _require_session(event)
        if denied is not None:
            logger.warning("unauthenticated_request path=%s", path)
            return denied

    try:
        if scheduled or (method == "POST" and path == "/sync"):
            body = sync_all()
        elif method == "POST" and path == "/sync/schemas":
            body = bootstrap_schemas()
        elif method == "POST" and path == "/sync/detect-transfers":
            body = detect_transfers()
        elif method == "POST" and path == "/sync/reprocess":
            body = reprocess()
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

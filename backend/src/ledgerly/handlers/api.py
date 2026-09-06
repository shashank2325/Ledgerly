"""HTTP API handler behind API Gateway (HTTP API v2, payload format 2.0).

Routing lives here rather than in Terraform so the API contract stays
independent of the infrastructure (SPEC §30) — the frontend must not care
whether this runs on Lambda today or ECS later.

Phase 2 serves health and metadata only. Real endpoints arrive in Phase 5.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

from ledgerly import __version__
from ledgerly.config import get_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"content-type": "application/json"}

Handler = Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": JSON_HEADERS,
        "body": json.dumps(body, separators=(",", ":")),
    }


# ── Routes ──────────────────────────────────────────────────────────────────


def health(_event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Liveness. Deliberately touches no downstream service so it stays fast
    and cannot fail for reasons unrelated to the function itself."""
    return 200, {"status": "ok", "version": __version__}


def readiness(_event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Reports whether the function is wired to its resources.

    Returns the NAMES of configured resources, never their contents, and never
    the Plaid secret ARN — this endpoint is unauthenticated in Phase 2.
    """
    cfg = get_config()
    wiring = {
        "accounts_table": bool(cfg.accounts_table),
        "rules_table": bool(cfg.rules_table),
        "data_bucket": bool(cfg.data_bucket),
        "plaid_secret": bool(cfg.plaid_secret_arn),
    }
    ready = all(wiring.values())
    return (200 if ready else 503), {
        "ready": ready,
        "environment": cfg.environment,
        "region": os.environ.get("AWS_REGION", "unknown"),
        "wiring": wiring,
    }


def list_accounts(_event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Accounts with balances, grouped-ready for the Accounts page.

    Served from DynamoDB, not Athena: this is operational state and a
    per-request Athena scan would be both slower and needlessly expensive
    (SPEC §8).

    Money is serialized as a STRING so it survives the wire without passing
    through JavaScript's float — `0.1 + 0.2 !== 0.3` and balances must be exact.
    """
    from ledgerly.storage import AccountRepository

    cfg = get_config()
    accounts = AccountRepository(cfg.accounts_table).list_all()

    payload = [
        {
            "account_id": a.account_id,
            "item_id": a.item_id,
            "institution_name": a.institution_name,
            "name": a.name,
            "mask": a.mask,
            "account_type": str(a.account_type),
            "account_subtype": a.account_subtype,
            "current_balance": str(a.current_balance) if a.current_balance is not None else None,
            "available_balance": str(a.available_balance) if a.available_balance is not None else None,
            "credit_limit": str(a.credit_limit) if a.credit_limit is not None else None,
            "iso_currency_code": a.iso_currency_code,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            "is_liability": a.is_liability,
        }
        for a in sorted(accounts, key=lambda x: (x.is_liability, x.institution_name or "", x.name))
    ]

    # Computed server-side: financial logic does not belong in the frontend
    # (SPEC §3). is_liability drives the sign, never the balance's own sign.
    net_worth = sum(a.net_worth_contribution for a in accounts)

    return 200, {
        "accounts": payload,
        "net_worth": str(net_worth),
        "count": len(payload),
    }


ROUTES: dict[tuple[str, str], Handler] = {
    ("GET", "/"): health,
    ("GET", "/accounts"): list_accounts,
    ("GET", "/health"): health,
    ("GET", "/ready"): readiness,
}


# ── Entrypoint ──────────────────────────────────────────────────────────────


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    started = time.perf_counter()

    http = event.get("requestContext", {}).get("http", {})
    method: str = http.get("method", "GET")
    path: str = http.get("path", "/")
    request_id = getattr(context, "aws_request_id", None) or event.get("requestContext", {}).get(
        "requestId", "-"
    )

    # Structured log line. Method and path only — no query string, no headers,
    # no body. Those can carry account identifiers or tokens (SPEC §42).
    log_fields: dict[str, Any] = {
        "request_id": request_id,
        "method": method,
        "path": path,
    }

    route = ROUTES.get((method, path))

    try:
        if route is None:
            status, body = 404, {"error": "not_found", "path": path}
        else:
            status, body = route(event)
    except Exception:
        # Log the traceback for us; return an opaque message to the caller so
        # internals are never leaked over the wire.
        logger.exception("unhandled_error", extra=log_fields)
        status, body = 500, {"error": "internal_error", "request_id": request_id}

    log_fields["status"] = status
    log_fields["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    logger.info(json.dumps(log_fields))

    return _response(status, body)

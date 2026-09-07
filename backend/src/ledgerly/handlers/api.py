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
from ledgerly.auth import AuthError, issue_token, verify_credentials, verify_token
from ledgerly.config import get_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"content-type": "application/json"}

Handler = Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": JSON_HEADERS,
        "body": json.dumps(body, separators=(",", ":")),
    }


# ── Routes ──────────────────────────────────────────────────────────────────


# Routes reachable without a session. Everything else requires one — the
# default is CLOSED, so a new endpoint is protected unless deliberately opened.
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset({
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("POST", "/auth/login"),
})


def _bearer(event: dict[str, Any]) -> str | None:
    # API Gateway lowercases header names in payload format 2.0, but be lenient.
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    value = headers.get("authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def login(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Exchange credentials for a session token.

    Returns an identical error for every failure mode so the response cannot be
    used to enumerate valid usernames.
    """
    body = _parse_body(event)
    cfg = get_config()

    try:
        username = verify_credentials(
            str(body.get("username", "")),
            str(body.get("password", "")),
            secret_arn=cfg.auth_secret_arn,
        )
    except AuthError:
        return 401, {"error": "invalid_credentials"}

    token, expires_at = issue_token(username, secret_arn=cfg.auth_secret_arn)
    return 200, {"token": token, "expires_at": expires_at, "username": username}


def session(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Whether the presented token is still valid — used on app boot so a stale
    token shows the login screen instead of a wall of failed requests."""
    token = _bearer(event)
    if not token:
        return 401, {"error": "no_token"}
    try:
        username = verify_token(token, secret_arn=get_config().auth_secret_arn)
    except AuthError as exc:
        return 401, {"error": "invalid_token", "reason": str(exc)}
    return 200, {"username": username, "valid": True}


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


def _athena() -> Any:
    from ledgerly.analytics import AthenaClient

    cfg = get_config()
    return AthenaClient(workgroup=cfg.athena_workgroup, database=cfg.glue_database)


def list_transactions_route(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The Ledger page. Filters map straight onto SQL predicates."""
    from datetime import date

    from ledgerly.analytics.serving import list_transactions

    params = event.get("queryStringParameters") or {}

    # Validate dates before they reach a statement.
    for key in ("from", "to"):
        if params.get(key):
            try:
                date.fromisoformat(params[key])
            except ValueError:
                return 400, {"error": "invalid_date", "field": key}

    try:
        limit = int(params.get("limit", 200))
    except ValueError:
        return 400, {"error": "invalid_limit"}

    from ledgerly.analytics.cache import cached

    key = "txns:" + json.dumps(
        {k: params.get(k) for k in ("from", "to", "account", "category", "type", "search", "limit")},
        sort_keys=True,
    )
    return 200, cached(key, lambda: list_transactions(
        _athena(),
        get_config().glue_database,
        date_from=params.get("from"),
        date_to=params.get("to"),
        account_id=params.get("account"),
        category=params.get("category"),
        transaction_type=params.get("type"),
        search=params.get("search"),
        limit=limit,
    ))


def dashboard_route(_event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The Overview page.

    Net worth comes from DynamoDB account balances, not Athena: it is current
    operational state, not history, and the accounts table already holds it.
    """
    from datetime import date, timedelta
    from decimal import Decimal

    from ledgerly.analytics.serving import dashboard, net_worth_series
    from ledgerly.storage import AccountRepository

    cfg = get_config()
    today = date.today()
    accounts = AccountRepository(cfg.accounts_table).list_all()
    net_worth = sum(a.net_worth_contribution for a in accounts)

    from ledgerly.analytics.cache import cached

    athena = _athena()
    month_start = today.replace(day=1)

    def compute() -> dict[str, Any]:
        # Three independent pieces of work, so issue them together. Athena
        # costs ~1s of fixed overhead per query against an Iceberg table
        # regardless of scan size, so sequencing them is what makes the page
        # feel broken — a naive version of this took 11s. The latest-expense
        # probe runs speculatively alongside the current month: it is needed
        # only if this month turns out to be empty, and paying for it upfront
        # is cheaper than a second round trip when it is.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=3) as pool:
            current_f = pool.submit(
                dashboard, athena, cfg.glue_database,
                month_start=month_start.isoformat(), today=today.isoformat(),
            )
            series_f = pool.submit(
                net_worth_series, athena, cfg.glue_database,
                current_net_worth=net_worth, today=today.isoformat(),
            )
            latest_f = pool.submit(
                athena.query,
                f"""SELECT max(transaction_date) AS latest
                    FROM {cfg.glue_database}.transactions
                    WHERE status != 'REMOVED' AND transaction_type = 'EXPENSE'""",
            )
            result = current_f.result()
            series = series_f.result()
            latest_rows = latest_f.result()

        result["month"] = today.strftime("%B %Y")
        result["is_fallback_month"] = False

        # A dashboard whose panels are all empty because the month is young, or
        # because no sync has run, tells the reader nothing and reads as broken.
        # When the current month has no spending, fall back to the most recent
        # month that does — and SAY SO. Silently swapping the window would be
        # worse than showing nothing; labelling it is what makes it honest.
        if not result["spending_by_category"] and Decimal(result["month_spending"]) == 0:
            latest = latest_rows[0]["latest"] if latest_rows else None
            if latest:
                start_of = date.fromisoformat(latest).replace(day=1)
                if start_of != month_start:
                    following = (
                        start_of.replace(year=start_of.year + 1, month=1)
                        if start_of.month == 12
                        else start_of.replace(month=start_of.month + 1)
                    )
                    result = dashboard(
                        athena, cfg.glue_database,
                        month_start=start_of.isoformat(),
                        today=(following - timedelta(days=1)).isoformat(),
                    )
                    result["month"] = start_of.strftime("%B %Y")
                    result["is_fallback_month"] = True

        result["net_worth_series"] = series
        return result

    # Keyed by the day so a date rollover cannot serve yesterday's month.
    # Net worth and account count come from DynamoDB and are cheap, so they are
    # attached AFTER the cache: a balance refresh shows up immediately without
    # waiting for the analytics cache to expire.
    body = cached(f"dashboard:{today.isoformat()}", compute)

    body["net_worth"] = str(net_worth)
    body["account_count"] = len(accounts)
    return 200, body


def cash_flow_report(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Cash-flow report, Sankey-shaped.

    Aggregation happens in Athena — this is exactly the long-range analytical
    query Athena exists for, not an operational read (SPEC §8).
    """
    from datetime import date

    from ledgerly.analytics import AthenaClient, cash_flow

    params = event.get("queryStringParameters") or {}
    today = date.today()
    date_from = params.get("from") or today.replace(month=1, day=1).isoformat()
    date_to = params.get("to") or today.isoformat()

    # Validate rather than interpolate blindly: these reach a SQL statement.
    for value in (date_from, date_to):
        try:
            date.fromisoformat(value)
        except ValueError:
            return 400, {"error": "invalid_date", "detail": f"{value!r} is not YYYY-MM-DD"}

    from ledgerly.analytics.cache import cached

    cfg = get_config()

    def compute() -> dict[str, Any]:
        report = cash_flow(
            AthenaClient(workgroup=cfg.athena_workgroup, database=cfg.glue_database),
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "date_from": report.date_from,
            "date_to": report.date_to,
            # Money as strings — exact across the wire, never a JS float.
            "total_income": str(report.total_income),
            "total_expenses": str(report.total_expenses),
            "net_income": str(report.net_income),
            # null when the ratio is not meaningful — the UI renders "—"
            "savings_rate": str(report.savings_rate)
            if report.savings_rate is not None
            else None,
            "sankey": report.to_sankey(),
        }

    return 200, cached(f"cashflow:{date_from}:{date_to}", compute)


ROUTES: dict[tuple[str, str], Handler] = {
    ("GET", "/"): health,
    ("POST", "/auth/login"): login,
    ("GET", "/auth/session"): session,
    ("GET", "/accounts"): list_accounts,
    ("GET", "/transactions"): list_transactions_route,
    ("GET", "/dashboard"): dashboard_route,
    ("GET", "/reports/cash-flow"): cash_flow_report,
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
        if route is not None and (method, path) not in PUBLIC_ROUTES:
            token = _bearer(event)
            if not token:
                return _response(401, {"error": "authentication_required"})
            try:
                verify_token(token, secret_arn=get_config().auth_secret_arn)
            except AuthError:
                return _response(401, {"error": "invalid_or_expired_token"})

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

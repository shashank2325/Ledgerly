"""Plaid endpoints: link-token creation, public-token exchange, item listing.

Runs as a SEPARATE Lambda from the read API, with its own IAM role. This is the
enforcement of ADR 0004: the function serving browser reads has no path to an
access token, because it cannot read the items table or the Plaid secret at all.

Routes (mounted under /plaid by API Gateway):
    POST /plaid/link-token   -> { link_token, expiration }
    POST /plaid/exchange     -> { item_id, institution_name, accounts_added }
    GET  /plaid/items        -> { items: [...] }   (token-free projection)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from ledgerly.config import get_config
from ledgerly.pipeline import normalize_accounts
from ledgerly.plaid import PlaidClient, PlaidError
from ledgerly.storage import AccountRepository, ItemRepository, PlaidItem, get_plaid_credentials

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"content-type": "application/json"}

# Single-user for now (SPEC §31). Becomes the Cognito subject in Phase 9; the
# indirection exists so that change touches one constant.
DEFAULT_USER_ID = "ledgerly-owner"


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": JSON_HEADERS,
        "body": json.dumps(body, separators=(",", ":"), default=str),
    }


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


def _client() -> PlaidClient:
    cfg = get_config()
    return PlaidClient(get_plaid_credentials(cfg.plaid_secret_arn))


# ── Handlers ────────────────────────────────────────────────────────────────


def create_link_token(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Mint a Link token for the browser.

    The token is short-lived, single-use, and safe to send to the client — it is
    not a credential for the user's bank.
    """
    body = _parse_body(event)
    cfg = get_config()

    # An access_token in the request means update mode: re-authenticating an
    # existing item rather than adding a new one. The token is looked up
    # server-side from item_id — the browser never sends or sees one.
    item_id = body.get("item_id")
    access_token = None
    if item_id:
        item = ItemRepository(cfg.items_table).get(item_id)
        if item is None:
            return 404, {"error": "item_not_found", "item_id": item_id}
        access_token = item.access_token

    result = _client().create_link_token(
        client_user_id=DEFAULT_USER_ID,
        access_token=access_token,
    )
    return 200, {
        "link_token": result["link_token"],
        "expiration": result["expiration"],
        "mode": "update" if access_token else "create",
    }


def exchange_public_token(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Exchange a public token, then persist the item and its accounts.

    Idempotent by construction: Plaid returns the SAME item_id for a
    re-linked institution, and both writes are upserts keyed on stable ids, so
    replaying this call cannot create a duplicate item or duplicate accounts
    (SPEC §41).
    """
    body = _parse_body(event)
    public_token = body.get("public_token")
    if not public_token:
        return 400, {"error": "missing_public_token"}

    cfg = get_config()
    client = _client()

    exchanged = client.exchange_public_token(public_token)
    access_token = exchanged["access_token"]
    item_id = exchanged["item_id"]

    # Resolve the institution for display. Non-fatal: a missing name must not
    # abort a successful link.
    institution_id = None
    institution_name = None
    try:
        item_info = client.get_item(access_token)
        institution_id = (item_info.get("item") or {}).get("institution_id")
        if institution_id:
            institution = client.get_institution(institution_id)
            institution_name = (institution.get("institution") or {}).get("name")
    except PlaidError as exc:
        logger.warning("institution_lookup_failed item_id=%s code=%s", item_id, exc.error_code)

    items = ItemRepository(cfg.items_table)
    existing = items.get(item_id)

    # ── Duplicate-institution guard ──────────────────────────────────────────
    # Plaid returns a fresh item_id (and fresh account_ids) for every completed
    # Link, even for an already-connected bank. Accepting both would create two
    # copies of every account and double-count net worth — the exact failure
    # this product exists to prevent.
    #
    # Not an outright block: a second login at the same institution is
    # legitimate (personal + business). The client must opt in explicitly.
    if existing is None and institution_id and not body.get("force"):
        duplicate = items.find_active_by_institution(institution_id)
        if duplicate is not None:
            # Hand the just-minted token back to Plaid rather than orphaning it.
            try:
                client.remove_item(access_token)
            except PlaidError as exc:
                logger.warning("orphan_item_cleanup_failed code=%s", exc.error_code)
            return 409, {
                "error": "institution_already_connected",
                "institution_name": duplicate.institution_name,
                "existing_item_id": duplicate.item_id,
                "hint": "Resend with force=true to add a second login at this institution.",
            }

    items.put(
        PlaidItem(
            item_id=item_id,
            access_token=access_token,
            institution_id=institution_id,
            institution_name=institution_name,
            # Preserve the cursor on re-link: discarding it would trigger a full
            # historical re-fetch and risk duplicating work already done.
            sync_cursor=existing.sync_cursor if existing else None,
            last_synced_at=existing.last_synced_at if existing else None,
            status="ACTIVE",
            created_at=existing.created_at if existing else datetime.now(UTC).isoformat(),
        )
    )

    accounts = normalize_accounts(
        client.get_accounts(access_token).get("accounts", []),
        item_id=item_id,
        institution_id=institution_id,
        institution_name=institution_name,
    )
    AccountRepository(cfg.accounts_table).put_many(accounts)

    return 200, {
        "item_id": item_id,
        "institution_name": institution_name,
        "accounts_added": len(accounts),
        "relinked": existing is not None,
    }


def list_items(_event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Connected institutions. Uses the token-free projection by construction."""
    cfg = get_config()
    items = ItemRepository(cfg.items_table).list_all()
    return 200, {"items": [item.to_public_dict() for item in items]}


ROUTES = {
    ("POST", "/plaid/link-token"): create_link_token,
    ("POST", "/plaid/exchange"): exchange_public_token,
    ("GET", "/plaid/items"): list_items,
}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "GET")
    path = http.get("path", "/")
    request_id = getattr(context, "aws_request_id", None) or "-"

    route = ROUTES.get((method, path))

    try:
        if route is None:
            status, body = 404, {"error": "not_found", "path": path}
        else:
            status, body = route(event)

    except PlaidError as exc:
        # Plaid's own errors are surfaced with their code so the UI can react
        # (e.g. prompt a reconnect), but never with internal detail.
        logger.warning(
            "plaid_error path=%s code=%s type=%s status=%d",
            path, exc.error_code, exc.error_type, exc.status,
        )
        status = 502 if exc.status >= 500 or exc.status == 0 else 400
        body = {
            "error": "plaid_error",
            "error_code": exc.error_code,
            "reconnect_required": exc.is_item_login_required,
        }

    except ValueError as exc:
        # Raised by PlaidCredentials when the selected environment's secret is
        # empty — the deliberate safe state. Give an actionable message.
        logger.error("configuration_error path=%s: %s", path, exc)
        status, body = 503, {"error": "configuration_error", "detail": str(exc)}

    except Exception:
        logger.exception("unhandled_error path=%s", path)
        status, body = 500, {"error": "internal_error", "request_id": request_id}

    logger.info(
        json.dumps({
            "request_id": request_id, "method": method, "path": path,
            "status": status, "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        })
    )
    return _response(status, body)

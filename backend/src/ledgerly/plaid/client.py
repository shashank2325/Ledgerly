"""Minimal Plaid API client. No third-party dependencies (ADR 0006).

Security rules this module enforces:
  - credentials are injected into the request body and NEVER logged
  - access tokens never appear in an exception message or a log line
  - the API version is pinned, so Plaid cannot silently change shapes on us
"""

from __future__ import annotations

import json
import logging
import os
import random
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Pinned deliberately. Without this header Plaid applies its own default, which
# can change under us and alter response shapes (ADR 0006).
PLAID_API_VERSION = "2020-09-14"

VALID_ENVIRONMENTS = ("sandbox", "production")

# Transient conditions worth retrying. 429 is included because Plaid rate-limits
# per-item and a sync burst can legitimately trip it.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4


class PlaidError(RuntimeError):
    """A Plaid API error.

    Carries the structured fields Plaid returns so callers can branch on
    `error_code` rather than parsing strings.
    """

    def __init__(
        self,
        status: int,
        error_code: str | None,
        error_type: str | None,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status = status
        self.error_code = error_code
        self.error_type = error_type
        self.request_id = request_id
        super().__init__(f"[{status}] {error_code or 'UNKNOWN'}: {message}")

    @property
    def is_item_login_required(self) -> bool:
        """The user must re-authenticate this item. Not retryable; the UI has to
        surface a reconnect prompt."""
        return self.error_code == "ITEM_LOGIN_REQUIRED"

    @property
    def is_rate_limited(self) -> bool:
        return self.error_code == "RATE_LIMIT_EXCEEDED" or self.status == 429


@dataclass(frozen=True, slots=True)
class PlaidCredentials:
    client_id: str
    secret: str
    environment: str

    def __post_init__(self) -> None:
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {VALID_ENVIRONMENTS}, got {self.environment!r}"
            )
        if not self.client_id or not self.secret:
            # Fail loudly at construction rather than as an opaque 400 from
            # Plaid. An empty sandbox_secret is the expected state before the
            # operator populates it, and this is where that surfaces.
            raise ValueError(
                f"Plaid credentials incomplete for environment={self.environment} "
                "(client_id or secret is empty)"
            )

    @property
    def base_url(self) -> str:
        return f"https://{self.environment}.plaid.com"


class PlaidClient:
    """Synchronous Plaid client.

    One instance per Lambda invocation; cheap to construct.
    """

    def __init__(self, credentials: PlaidCredentials, timeout: int = 25) -> None:
        self._creds = credentials
        self._timeout = timeout
        # Lambda's runtime trusts the system store. macOS python.org builds do
        # NOT read the system keychain, so local development can point at a
        # certifi bundle via SSL_CERT_FILE without changing any code path.
        self._ssl = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))

    # ── Transport ───────────────────────────────────────────────────────────

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "client_id": self._creds.client_id,
            "secret": self._creds.secret,
            **body,
        }
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Plaid-Version": PLAID_API_VERSION,
        }

        last_error: PlaidError | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = urllib.request.Request(
                f"{self._creds.base_url}{path}", data=data, headers=headers
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self._timeout, context=self._ssl
                ) as response:
                    return json.loads(response.read())

            except urllib.error.HTTPError as exc:
                detail = self._parse_error(exc)
                if detail.status not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                    raise detail from None
                last_error = detail

            except urllib.error.URLError as exc:
                # A TLS verification failure is a misconfiguration, not a blip.
                # Retrying it burns ~10s of a user-facing request to arrive at
                # the same answer, and buries the real cause behind backoff
                # noise. Fail immediately with an actionable code.
                if isinstance(exc.reason, ssl.SSLCertVerificationError):
                    raise PlaidError(
                        0, "TLS_VERIFICATION_FAILED", None,
                        f"{exc.reason} — set SSL_CERT_FILE to a CA bundle for local runs",
                    ) from None

                # Genuinely transient: DNS hiccup, connection reset, timeout.
                if attempt == MAX_ATTEMPTS:
                    raise PlaidError(0, "NETWORK_ERROR", None, str(exc.reason)) from None
                last_error = PlaidError(0, "NETWORK_ERROR", None, str(exc.reason))

            # Exponential backoff with full jitter: prevents a retry storm from
            # several items syncing at once re-colliding in lockstep.
            sleep_for = min(2**attempt, 8) * (0.5 + random.random() / 2)
            logger.warning(
                "plaid_retry path=%s attempt=%d/%d status=%s sleep=%.2fs",
                path,
                attempt,
                MAX_ATTEMPTS,
                last_error.status if last_error else "?",
                sleep_for,
            )
            time.sleep(sleep_for)

        raise last_error or PlaidError(0, "UNKNOWN", None, "request failed")

    @staticmethod
    def _parse_error(exc: urllib.error.HTTPError) -> PlaidError:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = {}
        return PlaidError(
            status=exc.code,
            error_code=body.get("error_code"),
            error_type=body.get("error_type"),
            # Plaid's display_message is user-safe; error_message is for us.
            message=body.get("error_message") or exc.reason or "unknown error",
            request_id=body.get("request_id"),
        )

    # ── Endpoints ───────────────────────────────────────────────────────────

    def create_link_token(
        self,
        client_user_id: str,
        *,
        client_name: str = "Ledgerly",
        products: tuple[str, ...] = ("transactions",),
        country_codes: tuple[str, ...] = ("US",),
        webhook: str | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """Create a Link token.

        Passing `access_token` puts Link in update mode, which is how a
        re-authentication (ITEM_LOGIN_REQUIRED) is resolved without creating a
        duplicate item.
        """
        body: dict[str, Any] = {
            "user": {"client_user_id": client_user_id},
            "client_name": client_name,
            "country_codes": list(country_codes),
            "language": "en",
        }
        if access_token:
            body["access_token"] = access_token
        else:
            # products is rejected by Plaid in update mode.
            body["products"] = list(products)
        if webhook:
            body["webhook"] = webhook
        return self._post("/link/token/create", body)

    def exchange_public_token(self, public_token: str) -> dict[str, Any]:
        """Exchange the short-lived public token for a permanent access token."""
        return self._post("/item/public_token/exchange", {"public_token": public_token})

    def get_accounts(self, access_token: str) -> dict[str, Any]:
        return self._post("/accounts/get", {"access_token": access_token})

    def get_item(self, access_token: str) -> dict[str, Any]:
        return self._post("/item/get", {"access_token": access_token})

    def remove_item(self, access_token: str) -> dict[str, Any]:
        """Invalidate an access token and disconnect the item at Plaid.

        Called when we reject a link we just created (duplicate institution).
        Without this the item lingers on Plaid's side — and in production Plaid
        bills per connected item, so an abandoned item is a recurring charge for
        something the user never sees.
        """
        return self._post("/item/remove", {"access_token": access_token})

    def get_institution(self, institution_id: str) -> dict[str, Any]:
        return self._post(
            "/institutions/get_by_id",
            {
                "institution_id": institution_id,
                "country_codes": ["US"],
                "options": {"include_optional_metadata": True},
            },
        )

    def transactions_sync(
        self, access_token: str, cursor: str | None = None, count: int = 500
    ) -> dict[str, Any]:
        """Incremental transaction sync (SPEC §12).

        `cursor` of None requests the historical baseline. Plaid paginates via
        `has_more`; the caller must loop until it is false, threading the
        returned `next_cursor` back in.
        """
        body: dict[str, Any] = {"access_token": access_token, "count": count}
        if cursor:
            body["cursor"] = cursor
        return self._post("/transactions/sync", body)

    # ── Sandbox-only helpers ────────────────────────────────────────────────

    def sandbox_create_public_token(
        self, institution_id: str, products: tuple[str, ...] = ("transactions",)
    ) -> dict[str, Any]:
        """Skip the Link UI. Sandbox only — guarded so it can never fire against
        production credentials."""
        if self._creds.environment != "sandbox":
            raise RuntimeError("sandbox_create_public_token is sandbox-only")
        return self._post(
            "/sandbox/public_token/create",
            {"institution_id": institution_id, "initial_products": list(products)},
        )

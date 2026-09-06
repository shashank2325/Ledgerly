"""Password verification and signed session tokens.

No third-party dependencies — scrypt and hmac are both stdlib, so this adds
nothing to the Lambda package (consistent with ADR 0006).

Design notes:
  - the password is never stored, logged, or returned; only its scrypt hash
    lives in Secrets Manager
  - comparisons are constant-time, so response latency cannot be used to
    discover a password character by character
  - session tokens are HMAC-signed with an independent key and carry an expiry,
    so a leaked token dies on its own and cannot be forged or extended
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from functools import lru_cache
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication failure.

    Deliberately carries no detail about WHY. Distinguishing "no such user"
    from "wrong password" tells an attacker which usernames exist.
    """


@lru_cache(maxsize=2)
def _load(secret_arn: str) -> dict[str, Any]:
    """Cached for the container's life — the credential does not change
    mid-invocation, and Secrets Manager bills per call."""
    raw = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    return json.loads(raw["SecretString"])


def _b64d(value: str) -> bytes:
    return base64.b64decode(value)


def verify_credentials(username: str, password: str, *, secret_arn: str) -> str:
    """Check a login. Returns the username on success, raises AuthError otherwise.

    The scrypt work is performed even when the username is wrong, so both
    failure modes take the same time.
    """
    config = _load(secret_arn)

    expected_hash = _b64d(config["hash"])
    salt = _b64d(config["salt"])

    candidate = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=config.get("n", 2**14),
        r=config.get("r", 8),
        p=config.get("p", 1),
        dklen=config.get("dklen", 32),
    )

    username_ok = hmac.compare_digest(username.encode(), config["username"].encode())
    password_ok = hmac.compare_digest(candidate, expected_hash)

    # Combined after both comparisons run, so neither short-circuits.
    if not (username_ok and password_ok):
        logger.warning("auth_failed")  # no username, no password, no reason
        raise AuthError("invalid credentials")

    return config["username"]


def issue_token(username: str, *, secret_arn: str) -> tuple[str, int]:
    """Mint a signed session token. Returns (token, expires_at_epoch).

    Format: base64(payload).base64(hmac). Not a JWT — there is no algorithm
    field to confuse, which removes the entire `alg: none` class of bug.
    """
    config = _load(secret_arn)
    ttl = int(config.get("session_ttl_seconds", 43200))
    expires_at = int(time.time()) + ttl

    payload = json.dumps(
        {"sub": username, "exp": expires_at}, separators=(",", ":")
    ).encode()
    signature = hmac.new(
        _b64d(config["session_signing_key"]), payload, hashlib.sha256
    ).digest()

    token = (
        base64.urlsafe_b64encode(payload).decode().rstrip("=")
        + "."
        + base64.urlsafe_b64encode(signature).decode().rstrip("=")
    )
    return token, expires_at


def _b64d_padded(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_token(token: str, *, secret_arn: str) -> str:
    """Validate a session token. Returns the subject, or raises AuthError.

    The signature is checked BEFORE the payload is parsed, so unsigned input
    never reaches the JSON decoder.
    """
    config = _load(secret_arn)

    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _b64d_padded(encoded_payload)
        signature = _b64d_padded(encoded_signature)
    except Exception:
        raise AuthError("malformed token") from None

    expected = hmac.new(
        _b64d(config["session_signing_key"]), payload, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(signature, expected):
        raise AuthError("bad signature")

    try:
        claims = json.loads(payload)
    except Exception:
        raise AuthError("malformed payload") from None

    if int(claims.get("exp", 0)) < time.time():
        raise AuthError("expired")

    return str(claims.get("sub", ""))

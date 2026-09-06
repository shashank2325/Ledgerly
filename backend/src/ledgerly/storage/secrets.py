"""Secrets Manager access.

One secret holds credentials for every Plaid environment; the `environment`
field selects which is used (ADR 0004). This module is the ONLY place that
reads it, and the value never leaves as a return type wider than
`PlaidCredentials`.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import boto3

from ledgerly.plaid.client import PlaidCredentials

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _fetch_secret(secret_arn: str) -> dict[str, str]:
    """Cached for the life of the Lambda container.

    Secrets Manager charges per API call and the credential does not change
    within an invocation. A rotation takes effect on the next cold start, which
    is acceptable for a credential rotated by hand.
    """
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])


def get_plaid_credentials(secret_arn: str) -> PlaidCredentials:
    """Resolve the credentials for the environment the secret is configured for.

    Raises ValueError (via PlaidCredentials) when the selected environment's
    secret is empty — which is the deliberate safe state when only one
    environment has been populated.
    """
    raw = _fetch_secret(secret_arn)
    environment = raw.get("environment", "sandbox")

    # Per-environment keys, so promoting to production is a one-field change and
    # never a copy-paste of a credential.
    secret = raw.get(f"{environment}_secret", "")

    logger.info("plaid_credentials_loaded environment=%s", environment)
    return PlaidCredentials(
        client_id=raw.get("client_id", ""),
        secret=secret,
        environment=environment,
    )

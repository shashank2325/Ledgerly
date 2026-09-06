"""Runtime configuration, read from the environment.

Nothing here holds a secret value — only ARNs and resource names. Secrets are
fetched at call time from Secrets Manager by the components entitled to them
(SPEC §32: no secrets in environment variables).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class Config:
    environment: str
    # Holds Plaid access tokens. Only the Plaid Lambda's role can read the
    # underlying table at all (ADR 0004) — the API Lambda leaves this empty.
    items_table: str
    accounts_table: str
    rules_table: str
    sync_runs_table: str
    data_bucket: str
    athena_results_bucket: str
    athena_workgroup: str
    glue_database: str
    plaid_secret_arn: str

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Cached across warm invocations — the environment cannot change mid-container."""
    return Config(
        environment=_env("LEDGERLY_ENV", "local"),
        items_table=_env("ITEMS_TABLE"),
        accounts_table=_env("ACCOUNTS_TABLE"),
        rules_table=_env("RULES_TABLE"),
        sync_runs_table=_env("SYNC_RUNS_TABLE"),
        data_bucket=_env("DATA_BUCKET"),
        athena_results_bucket=_env("ATHENA_RESULTS_BUCKET"),
        athena_workgroup=_env("ATHENA_WORKGROUP"),
        glue_database=_env("GLUE_DATABASE"),
        plaid_secret_arn=_env("PLAID_SECRET_ARN"),
    )

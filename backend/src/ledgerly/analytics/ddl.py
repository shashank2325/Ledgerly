"""Apply the Iceberg table DDL held in data/schemas/*.sql.

The .sql files are the single source of truth for the analytical schema. They
carry placeholders that are substituted here so the same file works for any
environment.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ledgerly.analytics.athena import AthenaClient

logger = logging.getLogger(__name__)

# Order matters only in that transactions is the table everything else refers
# to conceptually; there are no FK constraints in Iceberg.
SCHEMA_FILES = (
    "finance_transactions.sql",
    "finance_transfer_groups.sql",
    "finance_accounts_snapshot.sql",
)


def _strip_comments(sql: str) -> str:
    """Remove -- comments. Athena tolerates them, but stripping keeps the
    statements readable in logs and avoids a trailing-comment statement."""
    return "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )


def render(sql: str, *, data_bucket: str, database: str) -> list[str]:
    """Substitute placeholders and split into individual statements."""
    sql = sql.replace("REPLACE_ME_DATA_BUCKET", data_bucket)
    # The DDL is written as `finance.<table>`; the real database name is
    # environment-scoped (ledgerly_dev), so rewrite the qualifier.
    sql = re.sub(r"\bfinance\.", f"{database}.", sql)
    sql = _strip_comments(sql)
    return [s.strip() for s in sql.split(";") if s.strip()]


def _find_schema_dir() -> Path:
    """Locate the DDL.

    In Lambda the .sql files are staged into the package at ledgerly/schemas/.
    Running locally from a checkout, they are at data/schemas/. Check the
    packaged location first so the deployed path is the one exercised most.
    """
    packaged = Path(__file__).resolve().parent.parent / "schemas"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[4] / "data" / "schemas"


def apply_schemas(
    client: AthenaClient,
    *,
    data_bucket: str,
    database: str,
    schema_dir: Path | None = None,
) -> dict[str, str]:
    """Create any missing tables. Idempotent — every statement is
    CREATE TABLE IF NOT EXISTS or an idempotent ALTER."""
    directory = schema_dir or _find_schema_dir()
    results: dict[str, str] = {}

    for filename in SCHEMA_FILES:
        path = directory / filename
        if not path.exists():
            results[filename] = "MISSING"
            logger.warning("schema_file_missing path=%s", path)
            continue

        for statement in render(
            path.read_text(), data_bucket=data_bucket, database=database
        ):
            client.execute(statement)
        results[filename] = "OK"
        logger.info("schema_applied file=%s", filename)

    return results

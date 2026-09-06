"""Athena client.

Athena is asynchronous: StartQueryExecution returns immediately and the caller
polls. This wraps that into a synchronous call with bounded waiting, because
every use here (DDL, MERGE, small reads) needs the result before continuing.

Per ADR 0001 this is also the WRITE path for Iceberg — MERGE INTO is how
pending->posted upserts and removals are applied atomically.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import boto3

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


class AthenaError(RuntimeError):
    def __init__(self, state: str, reason: str, query: str = "") -> None:
        self.state = state
        self.reason = reason
        # Truncated: a MERGE statement can be thousands of characters and the
        # full text in an exception message is noise in CloudWatch.
        self.query_excerpt = query[:300]
        super().__init__(f"Athena {state}: {reason}")


class AthenaClient:
    def __init__(
        self,
        workgroup: str,
        database: str,
        *,
        poll_interval: float = 0.5,
        timeout: float = 240.0,
    ) -> None:
        self._athena = boto3.client("athena")
        self._workgroup = workgroup
        self._database = database
        self._poll_interval = poll_interval
        self._timeout = timeout

    def execute(self, sql: str) -> str:
        """Run a statement to completion. Returns the query execution id.

        Raises AthenaError on failure rather than returning a status, so a
        failed MERGE can never be mistaken for a successful one — which would
        cause the caller to advance the sync cursor past unwritten data.
        """
        started = time.perf_counter()
        execution_id = self._athena.start_query_execution(
            QueryString=sql,
            WorkGroup=self._workgroup,
            QueryExecutionContext={"Database": self._database},
        )["QueryExecutionId"]

        # Backoff: most DDL finishes in well under a second, but a MERGE over a
        # large batch can take tens of seconds. Start tight, widen gradually.
        interval = self._poll_interval
        while True:
            execution = self._athena.get_query_execution(QueryExecutionId=execution_id)[
                "QueryExecution"
            ]
            status = execution["Status"]
            state = status["State"]

            if state in TERMINAL_STATES:
                if state != "SUCCEEDED":
                    raise AthenaError(
                        state, status.get("StateChangeReason", "unknown"), sql
                    )
                stats = execution.get("Statistics", {})
                logger.info(
                    "athena_ok id=%s ms=%s scanned_bytes=%s wall_ms=%d",
                    execution_id,
                    stats.get("TotalExecutionTimeInMillis"),
                    stats.get("DataScannedInBytes", 0),
                    (time.perf_counter() - started) * 1000,
                )
                return execution_id

            if time.perf_counter() - started > self._timeout:
                # Leave nothing running behind us — an abandoned query keeps
                # scanning and keeps billing.
                self._athena.stop_query_execution(QueryExecutionId=execution_id)
                raise AthenaError("TIMEOUT", f"exceeded {self._timeout}s", sql)

            time.sleep(interval)
            interval = min(interval * 1.4, 3.0)

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as dicts.

        Numeric columns come back as strings from Athena; decimals are parsed
        into Decimal, never float, so money keeps its exact representation.
        """
        execution_id = self.execute(sql)
        rows: list[dict[str, Any]] = []
        columns: list[dict[str, str]] = []
        paginator = self._athena.get_paginator("get_query_results")

        for page_index, page in enumerate(
            paginator.paginate(QueryExecutionId=execution_id)
        ):
            meta = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            columns = [{"name": c["Name"], "type": c["Type"]} for c in meta]
            data_rows = page["ResultSet"]["Rows"]
            # Athena repeats the header row as the first row of the FIRST page
            # only. Dropping it unconditionally would eat real data on page 2+.
            if page_index == 0:
                data_rows = data_rows[1:]

            for row in data_rows:
                values = row.get("Data", [])
                record: dict[str, Any] = {}
                for column, cell in zip(columns, values, strict=False):
                    raw = cell.get("VarCharValue")
                    record[column["name"]] = _coerce(raw, column["type"])
                rows.append(record)

        return rows


def _coerce(raw: str | None, athena_type: str) -> Any:
    if raw is None:
        return None
    if athena_type.startswith("decimal"):
        return Decimal(raw)
    if athena_type in ("integer", "int", "bigint", "smallint", "tinyint"):
        return int(raw)
    if athena_type == "boolean":
        return raw == "true"
    # Everything else (varchar, date, timestamp) stays a string; callers that
    # need a date parse it in their own domain terms.
    return raw

# ADR 0001 — Use Athena `MERGE INTO` for Iceberg writes

**Status:** Accepted · 2026-09-06
**Blocks:** Phase 4 (ingestion pipeline)

## Context

Lambda must write normalized transactions into `finance.transactions` (Iceberg). Plaid's
`/transactions/sync` returns `added`, `modified`, and `removed` sets, and a pending transaction
later becomes a posted one under a *different* `transaction_id`. So the write is not an append —
it is an upsert plus a delete, and it must be idempotent under retry.

Three options:

1. **PyIceberg direct writes from Lambda** — no extra service; but heavy dependency tree against
   the 250 MB unzipped Lambda limit, manual conflict handling, and upsert support that is still
   maturing.
2. **Athena `MERGE INTO`** — SQL-native, ACID, handles insert/update/delete in one atomic
   statement. Costs per query and scans data.
3. **Glue ETL job** — most capable, but a heavyweight service for a workload of a few hundred
   rows per sync, with cold starts measured in minutes.

## Decision

Use **Athena `MERGE INTO`**.

Lambda normalizes the sync payload, writes it to an S3 staging prefix, registers it as an external
staging table, and issues a single `MERGE INTO finance.transactions USING staging ON
transaction_id` statement.

## Rationale

- `MERGE INTO` is precisely the primitive the pending→posted problem calls for. Expressing it in
  SQL means no hand-rolled reconciliation logic, which is where correctness bugs would live.
- Idempotency is free: matching on `transaction_id` makes a replayed sync a no-op.
- Volume is tiny — a personal ledger is thousands of rows per year, so per-query cost is
  effectively noise (Athena bills per TB scanned; we will scan megabytes).
- Keeps Lambda dependencies to `boto3` and the Plaid SDK. No packaging pain.
- Athena is already a required component for analytics, so this adds no new service.

## Consequences

- Writes are asynchronous — Athena queries must be polled to completion. Sync Lambda needs a
  wait-and-verify step and a timeout well under the Lambda ceiling.
- Each `MERGE` produces new data files; small-file accumulation is real. Phase 9 adds a scheduled
  `OPTIMIZE ... REWRITE DATA` compaction job. Tracked in DESIGN.md T2.
- Athena DDL/DML is a hard dependency of the write path, not just the read path. Its IAM policy
  needs write access to the table's S3 location and the Glue catalog.
- Staging prefix needs an S3 lifecycle rule to expire objects after a few days.

## Revisit if

Sync volume grows enough that per-`MERGE` latency or cost becomes noticeable, or a multi-user
future makes concurrent writes to one table contend. Then reconsider PyIceberg or Glue.

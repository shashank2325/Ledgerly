# ADR 0003 — Partition Iceberg tables by `month(transaction_date)`

**Status:** Accepted · 2026-09-06
**Blocks:** Phase 4

## Context

SPEC §7 warns in both directions: partition deliberately for query patterns, but "do NOT create
excessive partitions" and avoid small-file problems. These pull against each other at personal
scale, where the dataset is genuinely small.

Realistic volume: ~200 transactions/month for one user, ~2,400/year, ~24,000 over a decade. Even
at 20 users that is ~48,000 rows/year — small by any analytical standard. A year of transactions
is a few hundred KB of Parquet.

Expected queries (SPEC §7): current month, previous month, last 30/90 days, a specific year, a
date range, per-account history, per-category spending, monthly summaries. Every one of these is
either bounded by a date range or is a monthly rollup.

Options considered:

- **`day(transaction_date)`** — 365 partitions/year holding ~7 rows each. Pathological small-file
  generation for no pruning benefit at this size.
- **`month(transaction_date)`** — 12 partitions/year, ~200 rows each. Aligns exactly with the
  dominant query shape.
- **`year(transaction_date)`** — coarse; a "current month" query scans the whole year.
- **No partitioning, sorted by date** — relies purely on Iceberg per-file min/max stats. Viable
  at this size but gives up the cheap win, and degrades if volume ever grows.

## Decision

Partition by **`month(transaction_date)`**, with a write sort order of
`transaction_date ASC, account_id ASC`.

## Rationale

- Monthly is the natural grain of the entire product. Nearly every dashboard number is
  month-scoped, so the partition boundary and the query boundary coincide.
- 12 partitions per year is nowhere near excessive; a decade is 120.
- Iceberg *hidden* partitioning means queries filter on `transaction_date` directly and pruning
  happens automatically — no partition column leaks into the schema or into queries.
- The sort order lets min/max statistics prune files *within* a partition too, so a "last 30 days"
  query spanning two months still reads only the relevant files.

Deliberately **not** partitioning by `account_id` or `category`. Both are low-cardinality
dimensions that would multiply partition count for pruning that column statistics already provide.
This is exactly the "do not automatically partition by every dimension" trap SPEC §7 names.

## Consequences

- Each sync writes a small file into the current month's partition. Over a month that is ~30 tiny
  files. Bounded, but it accumulates — a scheduled `OPTIMIZE finance.transactions REWRITE DATA`
  compaction job is required (DESIGN.md T2, Phase 9). Not urgent at this scale; do not skip it.
- Backfilling history writes across many partitions at once. Fine as a one-off.
- `finance.transfer_groups` partitions on `source_date` so a transfer sits in the month its
  source leg occurred, keeping it aligned with the transactions it references.

## Revisit if

Row counts reach the millions, or query profiling shows partition pruning is not the binding
constraint. At that point evaluate bucketing on `account_id`.

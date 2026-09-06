# Data Schemas

Source of truth for the analytical layer. **Design the schema before the pipeline** (SPEC §47.29).

| File | Table | Layer |
|---|---|---|
| `raw_plaid_transactions.md` | — (S3 JSON) | Raw, immutable |
| `finance_transactions.sql` | `finance.transactions` | Curated |
| `finance_transfer_groups.sql` | `finance.transfer_groups` | Curated |
| `finance_accounts_snapshot.sql` | `finance.accounts_snapshot` | Curated |

Derived/aggregate tables (`monthly_spending`, `cash_flow`, `net_worth`) arrive in T1 — they are
pure functions of the curated layer and are always rebuildable, so they are not designed yet.

## Conventions that apply to every table

**Money is `decimal(16,2)`.** Never `double`, never `float`. Binary floating point cannot
represent `0.10` exactly and financial sums must be exact.

**Amount sign: negative leaves the account, positive enters it.**
This is the *opposite* of Plaid's convention (Plaid: positive = outflow). The pipeline flips the
sign exactly once, at normalization, and every downstream consumer sees the normalized form.
A checking→savings transfer is therefore `-2000.00` on checking and `+2000.00` on savings, which
is what SPEC §17 describes and what a human expects.

**Timestamps are UTC `timestamp`. Dates are `date`.** A transaction's `transaction_date` is a
calendar date with no timezone — it is the date the bank assigned, not an instant.

**Nullable by default.** SPEC §16: "Do not assume all fields will always be populated."
Only `transaction_id`, `account_id`, `transaction_date`, and `amount` are guaranteed.

**Every row carries lineage.** `_ingested_at` and `_source_key` point back to the exact raw S3
object the row was derived from, so any curated row can be traced to its source payload.

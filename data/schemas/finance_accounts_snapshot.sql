-- ============================================================================
-- finance.accounts_snapshot — daily balance history.
--
-- Grain:  one row per account per day.
-- Why:    Plaid reports only the CURRENT balance. Net worth over time is
--         impossible to reconstruct after the fact, so we must capture it as
--         it happens. A daily EventBridge job appends one row per account.
--         Miss a day and that day is gone forever — this table is append-only
--         and genuinely irrecoverable, unlike everything else in the platform.
-- Writes: append-only INSERT. Never updated.
-- ============================================================================

CREATE TABLE IF NOT EXISTS finance.accounts_snapshot (

    snapshot_date               date,
    account_id                  string,
    item_id                     string,

    institution_name            string,
    account_name                string,
    account_mask                string,     -- last 4 only. Never the full number.

    -- depository | credit | loan | investment | other
    account_type                string,
    -- checking | savings | credit card | mortgage | ...
    account_subtype             string,

    -- Sign convention: as the institution reports it. A credit card with $1,500
    -- owed reports current_balance = 1500 (a positive number that is a
    -- LIABILITY). is_liability below is what net worth must key off — never
    -- infer asset vs. debt from the sign.
    -- decimal(19,4), NOT (16,2). Investment accounts carry sub-cent precision
    -- from fractional shares — a sandbox 401k reports 23631.9805. At (16,2)
    -- that truncates SILENTLY, which is the worst possible failure mode for a
    -- balance. Verified against live Plaid data, 2026-09-06.
    current_balance             decimal(19,4),
    available_balance           decimal(19,4),
    credit_limit                decimal(19,4),
    iso_currency_code           string,

    -- True for credit/loan. Net worth = sum(assets) - sum(liabilities).
    is_liability                boolean,

    _captured_at                timestamp,
    _source_key                 string
)
PARTITIONED BY (month(snapshot_date))
LOCATION 's3://REPLACE_ME_DATA_BUCKET/curated/accounts_snapshot/'
TBLPROPERTIES (
    'table_type'        = 'ICEBERG',
    'format'            = 'parquet',
    'write_compression' = 'zstd'
);

-- ============================================================================
-- finance.transfer_groups — the matched pairs. Ledgerly's differentiator.
--
-- Grain:  one row per matched transfer (a PAIR of transactions, not one).
-- Why a table and not just a column: a transfer is a RELATIONSHIP. Competing
--         products store it as a category label on a single transaction, which
--         is why they double-count (see DESIGN.md §1). Modelling the pair lets
--         us prove both legs cancel, and lets the UI draw the link.
-- Writes: Athena MERGE INTO on transfer_group_id.
-- ============================================================================

CREATE TABLE IF NOT EXISTS finance.transfer_groups (

    transfer_group_id           string,

    -- ── The two legs ────────────────────────────────────────────────────────
    -- Source = the account money LEFT (its transaction amount is negative).
    -- Destination = the account money ENTERED (amount positive).
    -- Both must exist for status = CONFIRMED.
    source_transaction_id       string,
    source_account_id           string,
    destination_transaction_id  string,
    destination_account_id      string,

    -- Absolute value of the movement. Always positive.
    -- INVARIANT: source.amount + destination.amount = 0. A group that violates
    -- this is a data-quality failure and must be surfaced, not silently kept.
    amount                      decimal(16,2),
    iso_currency_code           string,

    -- ── Match characteristics ───────────────────────────────────────────────
    -- INTERNAL_TRANSFER    checking -> savings, between own deposit accounts
    -- CREDIT_CARD_PAYMENT  checking -> card. The expense already happened at
    --                      purchase time; the payment must NOT be spending.
    -- LOAN_PAYMENT         checking -> loan principal
    transfer_kind               string,

    -- CONFIRMED  matched and trusted (auto above threshold, or user-confirmed)
    -- SUGGESTED  candidate shown to the user awaiting confirm/reject
    -- REJECTED   user said no. Kept so we never re-suggest the same pair.
    status                      string,

    -- 0.0-1.0. Drives auto-confirm vs. suggest. Threshold tuned in Phase 6
    -- against real data — sandbox transfer patterns are not representative.
    confidence                  decimal(5,4),
    -- AUTO_EXACT | AUTO_FUZZY | USER_MANUAL | RULE
    match_method                string,
    -- Days between the two legs. Same-day is the common case; cross-institution
    -- transfers routinely settle 1-3 days apart.
    date_gap_days               int,

    source_date                 date,
    destination_date            date,

    -- ── Audit ───────────────────────────────────────────────────────────────
    matched_at                  timestamp,
    confirmed_at                timestamp,
    confirmed_by                string,     -- 'system' | user id
    _processed_at               timestamp
)
PARTITIONED BY (month(source_date))
LOCATION 's3://REPLACE_ME_DATA_BUCKET/curated/transfer_groups/'
TBLPROPERTIES (
    'table_type'        = 'ICEBERG',
    'format'            = 'parquet',
    'write_compression' = 'zstd'
);

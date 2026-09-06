-- ============================================================================
-- finance.transactions — the curated ledger. The core table of the platform.
--
-- Grain:    one row per transaction, keyed by transaction_id.
-- Source:   raw/plaid/transactions/ (immutable JSON), via the normalize step.
-- Writes:   Athena MERGE INTO on transaction_id (see ADR 0001).
-- Rebuild:  fully reproducible from the raw layer. Safe to drop and rebuild.
-- ============================================================================

CREATE TABLE IF NOT EXISTS finance.transactions (

    -- ── Identity ────────────────────────────────────────────────────────────
    -- Plaid's transaction_id. Stable for a posted transaction. NOTE: a pending
    -- transaction and the posted transaction that replaces it have DIFFERENT
    -- ids — the link is pending_transaction_id below. This is the single most
    -- common source of duplicate-transaction bugs.
    transaction_id              string,
    account_id                  string,
    item_id                     string,

    -- ── Dates ───────────────────────────────────────────────────────────────
    -- transaction_date is the posted/settled date and the partition key.
    -- authorized_date is when the merchant authorised it — often 1-3 days
    -- earlier, frequently null. Report on transaction_date.
    transaction_date            date,
    authorized_date             date,

    -- ── Money ───────────────────────────────────────────────────────────────
    -- SIGN CONVENTION: negative = money left the account,
    --                  positive = money entered the account.
    -- This is FLIPPED from Plaid's raw convention. Flipped once, at normalize.
    -- VERIFIED against live sandbox data 2026-09-06: Plaid returns +6.33 for an
    -- Uber charge (outflow) and -500 for an airline refund (inflow).
    --
    -- (16,2) is correct HERE and deliberately narrower than the (19,4) used for
    -- balances: the Transactions product always returns 2dp currency amounts.
    -- Widening it would imply a precision we never populate.
    amount                      decimal(16,2),
    iso_currency_code           string,

    -- ── Description, as the source gave it ──────────────────────────────────
    -- Preserved verbatim so normalization is always re-derivable.
    description                 string,   -- Plaid `name` — the raw bank string
    merchant_name               string,   -- Plaid's cleaned merchant, nullable
    merchant_entity_id          string,   -- Plaid's stable merchant id, nullable

    -- ── Plaid classification, kept separate from ours ───────────────────────
    plaid_category_primary      string,   -- personal_finance_category.primary
    plaid_category_detailed     string,   -- personal_finance_category.detailed
    plaid_category_confidence   string,   -- VERY_HIGH | HIGH | MEDIUM | LOW
    payment_channel             string,   -- online | in store | other
    transaction_code            string,   -- transfer, payment, ... often null

    -- ── Lifecycle ───────────────────────────────────────────────────────────
    -- status: PENDING | POSTED | REMOVED
    -- REMOVED rows are tombstoned, never hard-deleted — a removal is itself a
    -- fact about the account's history and we keep it.
    is_pending                  boolean,
    status                      string,
    -- When Plaid posts a transaction that supersedes a pending one, the posted
    -- record carries the pending record's id here. The pipeline uses this to
    -- tombstone the pending row rather than leaving a duplicate behind.
    pending_transaction_id      string,

    -- ── Ledgerly-derived enrichment ─────────────────────────────────────────
    -- Everything below is computed by us and is safe to recompute wholesale.
    normalized_merchant         string,   -- 'AMZN Mktp US*1234' -> 'Amazon'
    category                    string,   -- our taxonomy, top level
    subcategory                 string,

    -- INCOME | EXPENSE | TRANSFER | REFUND | ADJUSTMENT | UNKNOWN  (SPEC §19)
    -- The one field every financial report must respect. Transfers are
    -- excluded from both income and expense totals — never double-counted.
    transaction_type            string,

    is_transfer                 boolean,
    -- Both legs of a matched transfer share this id (SPEC §17). Null when the
    -- transaction is not part of a matched pair.
    transfer_group_id           string,
    is_recurring                boolean,

    -- ── User overrides ──────────────────────────────────────────────────────
    -- When true, enrichment must NOT overwrite the field on reprocess. This is
    -- what makes "rebuild derived data from raw" safe — user intent survives.
    user_category_override      boolean,
    user_type_override          boolean,
    user_note                   string,

    -- ── Lineage & audit ─────────────────────────────────────────────────────
    _ingested_at                timestamp,  -- when the raw payload landed
    _processed_at               timestamp,  -- when this row was last normalized
    _source_key                 string,     -- exact S3 key of the raw payload
    _sync_cursor                string      -- Plaid cursor that produced it
)
PARTITIONED BY (month(transaction_date))
LOCATION 's3://REPLACE_ME_DATA_BUCKET/curated/transactions/'
TBLPROPERTIES (
    'table_type'                     = 'ICEBERG',
    'format'                         = 'parquet',
    'write_compression'              = 'zstd',
    -- 32 MB target. Our files will be far smaller than this at personal scale;
    -- the value matters once compaction runs (T2).
    'write_target_data_file_size_bytes' = '33554432',
    'format-version'                 = '2',
    -- Keep 90 days of snapshots: enough for time travel and rollback, bounded
    -- enough that metadata does not grow without limit.
    'vacuum_max_snapshot_age_seconds' = '7776000'
);

-- Sort order. Iceberg records per-file min/max for sorted columns, so ordering
-- by transaction_date makes date-range predicates prune files inside a
-- partition as well as across partitions.
ALTER TABLE finance.transactions
    WRITE ORDERED BY transaction_date ASC, account_id ASC;

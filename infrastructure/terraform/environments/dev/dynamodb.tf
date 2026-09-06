# ============================================================================
# DynamoDB — operational state only. Never analytics (SPEC §10).
#
# All tables are PAY_PER_REQUEST: at personal scale the read/write volume is a
# few hundred operations a day, which costs effectively nothing on-demand and
# would cost ~$5/month/table on the smallest provisioned capacity.
# ============================================================================

# ── Plaid items ─────────────────────────────────────────────────────────────
# One row per connected institution. Holds the sync cursor and the access-token
# reference. See ADR 0004 for why the access token itself lives here.
resource "aws_dynamodb_table" "items" {
  name         = "${local.prefix}-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "item_id"

  attribute {
    name = "item_id"
    type = "S"
  }

  # This table is the only record of which banks are connected and where each
  # sync left off. Losing it means re-linking every institution by hand.
  point_in_time_recovery { enabled = true }

  server_side_encryption { enabled = true }

  lifecycle {
    prevent_destroy = true
  }
}

# ── Accounts ────────────────────────────────────────────────────────────────
# Current balance and metadata per account. Rebuildable from Plaid, so no PITR.
resource "aws_dynamodb_table" "accounts" {
  name         = "${local.prefix}-accounts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "account_id"

  attribute {
    name = "account_id"
    type = "S"
  }

  # Listing a single item's accounts is the most common access pattern
  # (rendering the Accounts page grouped by institution).
  attribute {
    name = "item_id"
    type = "S"
  }

  global_secondary_index {
    name            = "item_id-index"
    hash_key        = "item_id"
    projection_type = "ALL"
  }

  server_side_encryption { enabled = true }
}

# ── Categorization rules ────────────────────────────────────────────────────
# User-authored and NOT reproducible from any source — a lost rule set is lost
# work, so this gets PITR despite being small.
resource "aws_dynamodb_table" "rules" {
  name         = "${local.prefix}-rules"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "rule_id"

  attribute {
    name = "rule_id"
    type = "S"
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }

  lifecycle {
    prevent_destroy = true
  }
}

# ── Sync run log ────────────────────────────────────────────────────────────
# One row per sync invocation: cursor in/out, counts, outcome. Drives the
# "last synced" UI and makes failed syncs debuggable without trawling logs.
resource "aws_dynamodb_table" "sync_runs" {
  name         = "${local.prefix}-sync-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "item_id"
  range_key    = "started_at"

  attribute {
    name = "item_id"
    type = "S"
  }

  attribute {
    name = "started_at"
    type = "S"
  }

  # Operational history, not financial history — 90 days is plenty and TTL
  # keeps the table from growing forever at zero cost.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption { enabled = true }
}

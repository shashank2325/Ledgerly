# ============================================================================
# S3 — the data lake, frontend assets, and Athena query results.
# All private, all encrypted, public access blocked (SPEC §32).
# ============================================================================

# ── Data lake ───────────────────────────────────────────────────────────────
# Holds raw/ (immutable Plaid payloads), curated/ (Iceberg tables),
# staging/ (Athena MERGE scratch), analytics/ (derived tables).
resource "aws_s3_bucket" "data" {
  bucket = local.data_bucket_name

  # The raw layer is the recoverable base of the entire platform. Everything
  # else can be rebuilt from it; it cannot be rebuilt from anything.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    # Reduces per-request KMS calls; irrelevant for AES256 but harmless and
    # correct if this is ever switched to aws:kms.
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  # staging/ holds throwaway inputs for Athena MERGE INTO (ADR 0001). Expire
  # them quickly — they are re-derivable from raw/ and would otherwise
  # accumulate one object per sync forever.
  rule {
    id     = "expire-merge-staging"
    status = "Enabled"
    filter { prefix = "staging/" }
    expiration { days = 7 }
  }

  # Iceberg rewrites produce orphaned versions on every MERGE; without this the
  # bucket grows unboundedly even though the table does not.
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }

  # NOTE: deliberately NO transition rule on raw/ or curated/. At personal scale
  # the data is a few MB; Glacier transitions would cost more in per-object
  # overhead than they save, and would make reprocessing slow (SPEC §37).
}

# ── Frontend assets ─────────────────────────────────────────────────────────
# Private. CloudFront (Phase 9) is the only public entry point (SPEC §32).
resource "aws_s3_bucket" "frontend" {
  bucket = local.frontend_bucket_name
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Athena query results ────────────────────────────────────────────────────
resource "aws_s3_bucket" "athena_results" {
  bucket = local.athena_bucket_name
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Query results are a cache, not data. Aggressive expiry keeps this bucket free.
resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    id     = "expire-query-results"
    status = "Enabled"
    filter {}
    expiration { days = 14 }
  }
}

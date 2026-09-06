# ============================================================================
# Glue Data Catalog + Athena — the analytical layer (SPEC §8, §9).
#
# Terraform owns the DATABASE and the WORKGROUP. It does NOT own the tables:
# Iceberg table definitions live as DDL in data/schemas/*.sql and are applied
# through Athena, because Iceberg's TBLPROPERTIES and hidden partitioning are
# expressed far more faithfully in SQL than through aws_glue_catalog_table.
# That keeps one source of truth for the schema instead of two drifting ones.
# ============================================================================

resource "aws_glue_catalog_database" "finance" {
  name        = "ledgerly_${var.environment}"
  description = "Ledgerly curated and derived financial tables (Iceberg)"

  # Iceberg writes its own metadata under the table location; the database
  # location is only a default for tables that do not specify one.
  location_uri = "s3://${aws_s3_bucket.data.id}/curated/"
}

resource "aws_athena_workgroup" "main" {
  name = "${local.prefix}-wg"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/query-results/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    # The single most important cost control in the system. A malformed query
    # that forgets a date predicate could otherwise scan everything; at 1 GB
    # this fails the query instead of quietly billing for it (SPEC §37).
    # Personal-scale scans are measured in megabytes, so this is ~1000x headroom.
    bytes_scanned_cutoff_per_query = 1073741824
  }

  # Workgroup deletion would orphan query history; force is required because
  # the workgroup accumulates named queries.
  force_destroy = true
}

output "glue_database" {
  value = aws_glue_catalog_database.finance.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.main.name
}

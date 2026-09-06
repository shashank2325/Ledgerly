# ============================================================================
# IAM — least privilege, one role per Lambda (SPEC §32).
#
# Phase 2 has a single API Lambda. The sync Lambda (Phase 4) gets its OWN role
# rather than sharing this one: it is the only thing that should ever read the
# Plaid secret or write to raw/, and that boundary is the point.
# ============================================================================

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api_lambda" {
  name               = "${local.prefix}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "api_lambda" {
  # ── Logging ───────────────────────────────────────────────────────────────
  # Scoped to this function's own log group, not "*".
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.api_lambda.arn}:*"]
  }

  # ── Operational reads ─────────────────────────────────────────────────────
  # The API serves account and rule data. It does NOT get access to the items
  # table, because that holds Plaid access tokens and the API has no business
  # reading them (SPEC §11: tokens never reach the browser).
  statement {
    sid    = "ReadOperationalState"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.accounts.arn,
      "${aws_dynamodb_table.accounts.arn}/index/*",
      aws_dynamodb_table.rules.arn,
      aws_dynamodb_table.sync_runs.arn,
    ]
  }

  # ── Analytical reads ──────────────────────────────────────────────────────
  # Reports aggregate over the full transaction history, which is exactly what
  # Athena is for (SPEC §8). Read-only: the API can query the curated layer but
  # cannot mutate it — only the sync Lambda writes.
  statement {
    sid    = "AthenaRead"
    effect = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
      "athena:GetWorkGroup",
    ]
    resources = [aws_athena_workgroup.main.arn]
  }

  statement {
    sid       = "AthenaResults"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [
      aws_s3_bucket.athena_results.arn,
      "${aws_s3_bucket.athena_results.arn}/*",
    ]
  }

  # Reading Iceberg data requires reading its metadata and the underlying files.
  statement {
    sid       = "CuratedRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/curated/*"]
  }

  statement {
    sid       = "CuratedList"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }

  statement {
    sid       = "GlueRead"
    effect    = "Allow"
    actions   = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables",
                 "glue:GetPartition", "glue:GetPartitions"]
    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      aws_glue_catalog_database.finance.arn,
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${aws_glue_catalog_database.finance.name}/*",
    ]
  }

  # Rules are user-editable through the API; accounts are not.
  statement {
    sid    = "WriteRules"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
    ]
    resources = [aws_dynamodb_table.rules.arn]
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name   = "${local.prefix}-api-lambda"
  role   = aws_iam_role.api_lambda.id
  policy = data.aws_iam_policy_document.api_lambda.json
}

# ============================================================================
# Sync Lambda — the ingestion pipeline (SPEC §12).
#
# Separate from both the read API and the Plaid link handler:
#   - it is triggered by webhook and schedule, not by a waiting human
#   - it needs a much longer timeout for the historical backfill
#   - it is the only thing that writes the raw layer or the Iceberg tables
#
# Splitting it keeps the blast radius of each role small, which is the whole
# point of ADR 0004.
# ============================================================================

resource "aws_iam_role" "sync_lambda" {
  name               = "${local.prefix}-sync-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "sync_lambda" {
  # The serving cache: read-through on the API, invalidated by writers.
  statement {
    sid    = "ServingCache"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.cache.arn]
  }

  statement {
    sid       = "Logs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.sync_lambda.arn}:*"]
  }

  # Verifying the caller's session token.
  statement {
    sid       = "ReadAuthSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.auth.arn]
  }

  statement {
    sid       = "ReadPlaidCredentials"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.plaid.arn]
  }

  # Reads access tokens; writes the sync cursor back after data is durable.
  statement {
    sid       = "ManageItems"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.items.arn]
  }

  statement {
    sid       = "WriteAccountsAndRuns"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                 "dynamodb:BatchWriteItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [
      aws_dynamodb_table.accounts.arn,
      "${aws_dynamodb_table.accounts.arn}/index/*",
      aws_dynamodb_table.sync_runs.arn,
    ]
  }

  # Raw is append-only in practice; staging is scratch for MERGE INTO; curated
  # is where Iceberg writes data and metadata.
  statement {
    sid    = "DataLakeAccess"
    effect = "Allow"
    actions = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject",
               "s3:AbortMultipartUpload"]
    resources = [
      "${aws_s3_bucket.data.arn}/raw/*",
      "${aws_s3_bucket.data.arn}/staging/*",
      "${aws_s3_bucket.data.arn}/curated/*",
    ]
  }

  statement {
    sid       = "DataLakeList"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }

  statement {
    sid    = "AthenaQuery"
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

  # Athena writes results here regardless of the query.
  statement {
    sid       = "AthenaResults"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [
      aws_s3_bucket.athena_results.arn,
      "${aws_s3_bucket.athena_results.arn}/*",
    ]
  }

  # Iceberg DDL and MERGE both mutate Glue catalog metadata.
  statement {
    sid    = "GlueCatalog"
    effect = "Allow"
    actions = [
      "glue:GetDatabase", "glue:GetDatabases",
      "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable",
      "glue:GetTable", "glue:GetTables",
      "glue:GetPartition", "glue:GetPartitions",
      "glue:BatchCreatePartition", "glue:UpdatePartition",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      aws_glue_catalog_database.finance.arn,
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${aws_glue_catalog_database.finance.name}/*",
    ]
  }
}

resource "aws_iam_role_policy" "sync_lambda" {
  name   = "${local.prefix}-sync-lambda"
  role   = aws_iam_role.sync_lambda.id
  policy = data.aws_iam_policy_document.sync_lambda.json
}

resource "aws_cloudwatch_log_group" "sync_lambda" {
  name              = "/aws/lambda/${local.prefix}-sync"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "sync" {
  function_name = "${local.prefix}-sync"
  role          = aws_iam_role.sync_lambda.arn
  handler       = "ledgerly.handlers.sync.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]

  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  # The historical backfill pages through Plaid and runs several Athena queries
  # per batch; Athena statements are polled to completion. 5 min leaves room
  # without approaching Lambda's 15 min ceiling.
  memory_size = 1024
  timeout     = 300

  environment {
    variables = {
      LEDGERLY_ENV          = var.environment
      ITEMS_TABLE           = aws_dynamodb_table.items.name
      ACCOUNTS_TABLE        = aws_dynamodb_table.accounts.name
      CACHE_TABLE        = aws_dynamodb_table.cache.name
      SYNC_RUNS_TABLE       = aws_dynamodb_table.sync_runs.name
      DATA_BUCKET           = aws_s3_bucket.data.id
      ATHENA_RESULTS_BUCKET = aws_s3_bucket.athena_results.id
      ATHENA_WORKGROUP      = aws_athena_workgroup.main.name
      GLUE_DATABASE         = aws_glue_catalog_database.finance.name
      PLAID_SECRET_ARN      = aws_secretsmanager_secret.plaid.arn
      AUTH_SECRET_ARN       = aws_secretsmanager_secret.auth.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.sync_lambda]
}

output "sync_lambda_name" {
  value = aws_lambda_function.sync.function_name
}

resource "aws_lambda_permission" "sync_api_gateway" {
  statement_id  = "AllowAPIGatewayInvokeSync"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "sync" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.sync.invoke_arn
  payload_format_version = "2.0"

  # Athena polling makes this the slowest path in the system; API Gateway's own
  # ceiling is 30s, so a long historical backfill must be driven by the
  # scheduled invocation rather than the HTTP trigger.
  timeout_milliseconds = 29000
}

resource "aws_apigatewayv2_route" "sync_root" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /sync"
  target    = "integrations/${aws_apigatewayv2_integration.sync.id}"
}

resource "aws_apigatewayv2_route" "sync_proxy" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /sync/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.sync.id}"
}

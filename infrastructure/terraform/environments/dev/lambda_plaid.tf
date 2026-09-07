# ============================================================================
# Plaid Lambda — link token, token exchange, item listing.
#
# A SEPARATE function with a SEPARATE role, deliberately. This is the
# enforcement mechanism for ADR 0004: the read API cannot reach an access token
# because its role has no permission on the items table or the Plaid secret.
# Merging these two functions would collapse that boundary, so they stay apart
# even though the code could trivially live together.
# ============================================================================

resource "aws_iam_role" "plaid_lambda" {
  name               = "${local.prefix}-plaid-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "plaid_lambda" {
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
    resources = ["${aws_cloudwatch_log_group.plaid_lambda.arn}:*"]
  }

  # Verifying the caller's session token.
  statement {
    sid       = "ReadAuthSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.auth.arn]
  }

  # The Plaid application credentials. Only this role may read them.
  statement {
    sid       = "ReadPlaidCredentials"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.plaid.arn]
  }

  # Access tokens live here. Read/write, but scoped to this one table.
  # DeleteItem is required to disconnect an institution — without it the item
  # row survives a removal and the connection appears to still exist.
  statement {
    sid    = "ManageItems"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.items.arn]
  }

  # Accounts are written on link and refreshed on sync.
  statement {
    sid    = "WriteAccounts"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.accounts.arn,
      "${aws_dynamodb_table.accounts.arn}/index/*",
    ]
  }

  # Removing an institution deletes its curated rows, which is Athena DDL/DML
  # against the Iceberg tables.
  statement {
    sid    = "AthenaDelete"
    effect = "Allow"
    actions = ["athena:StartQueryExecution", "athena:GetQueryExecution",
               "athena:GetQueryResults", "athena:StopQueryExecution", "athena:GetWorkGroup"]
    resources = [aws_athena_workgroup.main.arn]
  }

  statement {
    sid       = "AthenaResults"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.athena_results.arn, "${aws_s3_bucket.athena_results.arn}/*"]
  }

  statement {
    sid       = "CuratedWrite"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.data.arn}/curated/*"]
  }

  statement {
    sid       = "DataLakeList"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }

  statement {
    sid    = "GlueCatalog"
    effect = "Allow"
    actions = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables",
               "glue:UpdateTable", "glue:GetPartition", "glue:GetPartitions"]
    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      aws_glue_catalog_database.finance.arn,
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${aws_glue_catalog_database.finance.name}/*",
    ]
  }

  # Sync run bookkeeping (Phase 4).
  statement {
    sid       = "WriteSyncRuns"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.sync_runs.arn]
  }

  # Raw Plaid payloads land here before anything is normalized (SPEC §15).
  # Write and read only under raw/ — not the whole bucket.
  statement {
    sid       = "WriteRawLayer"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/raw/*"]
  }
}

resource "aws_iam_role_policy" "plaid_lambda" {
  name   = "${local.prefix}-plaid-lambda"
  role   = aws_iam_role.plaid_lambda.id
  policy = data.aws_iam_policy_document.plaid_lambda.json
}

resource "aws_cloudwatch_log_group" "plaid_lambda" {
  name              = "/aws/lambda/${local.prefix}-plaid"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "plaid" {
  function_name = "${local.prefix}-plaid"
  role          = aws_iam_role.plaid_lambda.arn
  handler       = "ledgerly.handlers.plaid_api.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]

  # Same artifact as the API Lambda — one build, two entrypoints. Possible only
  # because the Plaid client has no third-party dependencies (ADR 0006).
  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  memory_size = 512
  # Longer than the API's 15s: the exchange path makes four sequential Plaid
  # calls (exchange, item, institution, accounts) and a human is waiting.
  timeout = 30

  environment {
    variables = {
      LEDGERLY_ENV     = var.environment
      ITEMS_TABLE      = aws_dynamodb_table.items.name
      ACCOUNTS_TABLE   = aws_dynamodb_table.accounts.name
      CACHE_TABLE   = aws_dynamodb_table.cache.name
      SYNC_RUNS_TABLE  = aws_dynamodb_table.sync_runs.name
      DATA_BUCKET      = aws_s3_bucket.data.id
      PLAID_SECRET_ARN = aws_secretsmanager_secret.plaid.arn
      ATHENA_WORKGROUP = aws_athena_workgroup.main.name
      GLUE_DATABASE    = aws_glue_catalog_database.finance.name
      AUTH_SECRET_ARN  = aws_secretsmanager_secret.auth.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.plaid_lambda]
}

resource "aws_lambda_permission" "plaid_api_gateway" {
  statement_id  = "AllowAPIGatewayInvokePlaid"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.plaid.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "plaid" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.plaid.invoke_arn
  payload_format_version = "2.0"
}

# More specific than `/{proxy+}`, so HTTP API's most-specific-match routing
# sends /plaid/* here and everything else to the read API. Per-method for the
# same CORS-preflight reason documented in api_gateway.tf.
resource "aws_apigatewayv2_route" "plaid" {
  for_each  = toset(["GET", "POST"])
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "${each.value} /plaid/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.plaid.id}"
}

# ============================================================================
# Lambda — the API handler.
#
# ARM64 (Graviton): ~20% cheaper per GB-second than x86 with no code change,
# and the Python runtime supports it natively.
# ============================================================================

# Phase 2 packages only first-party code — boto3 ships in the Lambda runtime, so
# there are no third-party dependencies to vendor yet. The Plaid SDK arrives in
# Phase 3 and will need a build step or a layer.
data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${path.module}/../../../../backend/src"
  output_path = "${path.module}/.build/api.zip"
  excludes    = ["**/__pycache__", "**/*.pyc"]
}

resource "aws_lambda_function" "api" {
  function_name = "${local.prefix}-api"
  role          = aws_iam_role.api_lambda.arn
  handler       = "ledgerly.handlers.api.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]

  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  # 512 MB is the sweet spot: Lambda scales CPU with memory, so a larger size
  # often finishes faster and costs the SAME or less. 128 MB would be false
  # economy on JSON-heavy work.
  memory_size = 512
  timeout     = 15

  environment {
    variables = {
      LEDGERLY_ENV            = var.environment
      ACCOUNTS_TABLE          = aws_dynamodb_table.accounts.name
      RULES_TABLE             = aws_dynamodb_table.rules.name
      SYNC_RUNS_TABLE         = aws_dynamodb_table.sync_runs.name
      DATA_BUCKET             = aws_s3_bucket.data.id
      ATHENA_RESULTS_BUCKET   = aws_s3_bucket.athena_results.id
      # Only the ARN — the API role cannot read this secret, and the value is
      # never passed through the environment (SPEC §32: no secrets in env vars).
      PLAID_SECRET_ARN        = aws_secretsmanager_secret.plaid.arn
      POWERTOOLS_SERVICE_NAME = "ledgerly-api"
    }
  }

  # Explicit dependency: without it Lambda may create the log group implicitly
  # with no retention policy, and logs then accumulate forever.
  depends_on = [aws_cloudwatch_log_group.api_lambda]
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

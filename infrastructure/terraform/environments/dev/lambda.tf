# ============================================================================
# Lambda — the API handler.
#
# ARM64 (Graviton): ~20% cheaper per GB-second than x86 with no code change,
# and the Python runtime supports it natively.
# ============================================================================

# Phase 2 packages only first-party code — boto3 ships in the Lambda runtime, so
# there are no third-party dependencies to vendor yet. The Plaid SDK arrives in
# Phase 3 and will need a build step or a layer.
# No third-party dependencies to vendor: boto3 ships in the Lambda runtime and
# the Plaid client is stdlib-only (ADR 0006). So the package is first-party code
# plus the Iceberg DDL.
#
# The .sql files are staged into the build because data/schemas/ is their single
# source of truth (SPEC §47.29) and duplicating them into the Python package
# would let the two copies drift.
resource "null_resource" "stage_lambda_source" {
  triggers = {
    # Rebuild when any source or schema file changes.
    src_hash = sha1(join("", [
      for f in fileset("${path.module}/../../../../backend/src", "**/*.py") :
      filesha1("${path.module}/../../../../backend/src/${f}")
    ]))
    schema_hash = sha1(join("", [
      for f in fileset("${path.module}/../../../../data/schemas", "*.sql") :
      filesha1("${path.module}/../../../../data/schemas/${f}")
    ]))
  }

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      BUILD="${path.module}/.build/pkg"
      rm -rf "$BUILD" && mkdir -p "$BUILD"
      cp -R "${path.module}/../../../../backend/src/." "$BUILD/"
      mkdir -p "$BUILD/ledgerly/schemas"
      cp "${path.module}/../../../../data/schemas/"*.sql "$BUILD/ledgerly/schemas/"
      find "$BUILD" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
    CMD
  }
}

data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${path.module}/.build/pkg"
  output_path = "${path.module}/.build/api.zip"
  excludes    = ["**/__pycache__", "**/*.pyc"]

  depends_on = [null_resource.stage_lambda_source]
}

resource "aws_lambda_function" "api" {
  function_name = "${local.prefix}-api"
  role          = aws_iam_role.api_lambda.arn
  handler       = "ledgerly.handlers.api.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]

  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  # 512 MB, measured. Raising this to 1024 was tried and made no difference to
  # dashboard latency — the cost is Athena's fixed ~1.7s planning per query,
  # not CPU. Since Lambda bills GB-seconds, more memory with the same duration
  # is simply double the price for nothing.
  memory_size = 512
  timeout     = 15

  environment {
    variables = {
      LEDGERLY_ENV            = var.environment
      ACCOUNTS_TABLE          = aws_dynamodb_table.accounts.name
      CACHE_TABLE          = aws_dynamodb_table.cache.name
      RULES_TABLE             = aws_dynamodb_table.rules.name
      SYNC_RUNS_TABLE         = aws_dynamodb_table.sync_runs.name
      DATA_BUCKET             = aws_s3_bucket.data.id
      ATHENA_RESULTS_BUCKET   = aws_s3_bucket.athena_results.id
      ATHENA_WORKGROUP        = aws_athena_workgroup.main.name
      GLUE_DATABASE           = aws_glue_catalog_database.finance.name
      # Only the ARN — the API role cannot read this secret, and the value is
      # never passed through the environment (SPEC §32: no secrets in env vars).
      PLAID_SECRET_ARN        = aws_secretsmanager_secret.plaid.arn
      AUTH_SECRET_ARN         = aws_secretsmanager_secret.auth.arn
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

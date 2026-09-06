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

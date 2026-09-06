# ============================================================================
# CloudWatch and cost guardrails (SPEC §37, §42).
# ============================================================================

resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${local.prefix}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.prefix}"
  retention_in_days = var.log_retention_days
}

# ── Budget alert ────────────────────────────────────────────────────────────
# The safety net. A misconfigured Athena query scanning a full table, or a sync
# loop, are the realistic ways this project stops being a $1/month project.
resource "aws_budgets_budget" "monthly" {
  count = var.budget_alert_email != "" ? 1 : 0

  name         = "${local.prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Warn at 50% of forecast — early enough to intervene before the money is
  # actually spent, rather than after.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}

# ── Lambda error alarm ──────────────────────────────────────────────────────
# No SNS topic yet — the alarm is visible in the console and becomes actionable
# when notifications are wired up in Phase 9. Creating it now means the metric
# history exists when we need it.
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.prefix}-api-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "API Lambda erroring repeatedly"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

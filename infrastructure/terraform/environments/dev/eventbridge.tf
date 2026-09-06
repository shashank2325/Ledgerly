# ============================================================================
# Scheduled sync (SPEC §13, §36).
#
# Webhooks are the low-latency path but cannot be assumed reliable — a missed
# webhook would otherwise mean data never arrives. A periodic pull is the
# reconciliation backstop that makes the pipeline self-healing: because sync is
# incremental (cursor-based) and idempotent, running it on a timer costs
# almost nothing and silently repairs any gap.
# ============================================================================

variable "sync_schedule_enabled" {
  description = <<-EOT
    Whether to run the sync on a timer. OFF by default: while the pipeline is
    still being built, an unattended job that calls Plaid and runs Athena on a
    loop is a way to spend money on data nobody is looking at. Turn this on once
    real accounts are connected and the results are worth keeping fresh.

    With it off, sync runs only when invoked by hand — see infrastructure/README.
  EOT
  type        = bool
  default     = false
}

variable "sync_schedule" {
  description = <<-EOT
    How often to pull from Plaid. Every 3 hours by default: banks post
    transactions in batches over hours, not seconds, so anything tighter spends
    Plaid API calls to re-learn the same answer. Each run is a cursor-based
    incremental pull, so a no-op run is nearly free.
  EOT
  type        = string
  default     = "rate(3 hours)"
}

resource "aws_cloudwatch_event_rule" "scheduled_sync" {
  name                = "${local.prefix}-scheduled-sync"
  description         = "Incremental Plaid sync + reconciliation backstop"
  schedule_expression = var.sync_schedule

  # The rule is always created so enabling it later is a one-line change rather
  # than new infrastructure, but it fires nothing while disabled.
  state = var.sync_schedule_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "scheduled_sync" {
  rule      = aws_cloudwatch_event_rule.scheduled_sync.name
  target_id = "sync-lambda"
  arn       = aws_lambda_function.sync.arn

  # The handler treats an event with no requestContext as a scheduled full
  # sync, so no payload shaping is needed.
  input = jsonencode({ source = "eventbridge.schedule" })

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 2
  }
}

resource "aws_lambda_permission" "scheduled_sync" {
  statement_id  = "AllowEventBridgeInvokeSync"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduled_sync.arn
}

# A sync that stops running is invisible until someone notices stale data, so
# alarm on the absence of successful invocations rather than only on errors.
resource "aws_cloudwatch_metric_alarm" "sync_failures" {
  alarm_name          = "${local.prefix}-sync-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 10800
  statistic           = "Sum"
  threshold           = 2
  alarm_description   = "Scheduled Plaid sync failing repeatedly"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sync.function_name
  }
}

output "sync_schedule" {
  value = var.sync_schedule_enabled ? var.sync_schedule : "DISABLED (manual invocation only)"
}

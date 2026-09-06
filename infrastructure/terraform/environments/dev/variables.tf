variable "aws_region" {
  description = "AWS region. Athena, Iceberg, and Lambda all live here together."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name. Only 'dev' exists initially (SPEC §34)."
  type        = string
  default     = "dev"
}

variable "log_retention_days" {
  description = <<-EOT
    CloudWatch log retention. Short by default: logs are the main sneaky cost in
    a low-traffic serverless app, and dev logs older than two weeks are useless.
  EOT
  type        = number
  default     = 14
}

variable "budget_alert_email" {
  description = <<-EOT
    Email for the AWS Budgets alert (SPEC §37). Leave empty to skip creating the
    budget. Strongly recommended — this is the safety net against a runaway
    Athena scan or a sync loop.
  EOT
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly spend threshold that triggers the alert."
  type        = number
  default     = 10
}

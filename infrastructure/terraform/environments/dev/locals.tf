data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  prefix     = "ledgerly-${var.environment}"

  # S3 bucket names are globally unique across all AWS accounts, so they are
  # suffixed with the account id rather than a random string — that keeps them
  # deterministic and reproducible if state is ever rebuilt.
  data_bucket_name     = "${local.prefix}-data-${local.account_id}"
  frontend_bucket_name = "${local.prefix}-frontend-${local.account_id}"
  athena_bucket_name   = "${local.prefix}-athena-results-${local.account_id}"
}

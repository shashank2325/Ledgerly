# ============================================================================
# Bootstrap — creates the Terraform state backend itself.
#
# Chicken-and-egg: the state bucket cannot be managed by the state it stores.
# This config runs ONCE with local state, then dev/ uses the bucket it creates.
# Its own state file is trivial to recreate, so losing it is not a problem.
#
#   cd bootstrap && terraform init && terraform apply
# ============================================================================

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "ledgerly", ManagedBy = "terraform", Component = "bootstrap" }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "state" {
  bucket = "ledgerly-tfstate-${data.aws_caller_identity.current.account_id}"

  # State is recoverable infrastructure, not disposable. Refuse accidental
  # destruction of the bucket that describes everything else.
  lifecycle {
    prevent_destroy = true
  }
}

# Versioning is the actual disaster-recovery mechanism for Terraform state —
# a corrupted or truncated state file is restored by rolling back a version.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Expire old state versions after 90 days so the bucket does not grow forever.
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

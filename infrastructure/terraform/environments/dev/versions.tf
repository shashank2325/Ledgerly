terraform {
  required_version = ">= 1.10"

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }

  # State lives in S3, created by ../../bootstrap. `use_lockfile` uses S3-native
  # conditional writes for locking (Terraform >= 1.10), so no DynamoDB lock
  # table is needed — one less resource and one less thing to pay for.
  backend "s3" {
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
    # bucket is supplied by backend-config at init time (see README) because it
    # embeds the account id and must not be hardcoded in a committed file.
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "ledgerly"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

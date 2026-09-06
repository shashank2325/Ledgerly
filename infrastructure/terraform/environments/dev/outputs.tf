output "api_url" {
  description = "Base URL of the HTTP API. Set this as VITE_API_URL in the frontend."
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "data_bucket" {
  description = "Data lake bucket. Substitute for REPLACE_ME_DATA_BUCKET in data/schemas/*.sql."
  value       = aws_s3_bucket.data.id
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.id
}

output "athena_results_bucket" {
  value = aws_s3_bucket.athena_results.id
}

output "plaid_secret_id" {
  description = "Secrets Manager id to populate with Plaid credentials."
  value       = aws_secretsmanager_secret.plaid.name
}

output "dynamodb_tables" {
  value = {
    items     = aws_dynamodb_table.items.name
    accounts  = aws_dynamodb_table.accounts.name
    rules     = aws_dynamodb_table.rules.name
    sync_runs = aws_dynamodb_table.sync_runs.name
  }
}

output "lambda_function_name" {
  value = aws_lambda_function.api.function_name
}

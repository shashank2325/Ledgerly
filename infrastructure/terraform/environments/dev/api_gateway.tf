# ============================================================================
# API Gateway — HTTP API (v2), not REST API (v1).
#
# HTTP API is ~70% cheaper ($1.00 vs $3.50 per million requests), has lower
# latency, and natively supports JWT authorizers — which is what Cognito
# integration in Phase 9 will need. REST API's extra features (request
# validation models, WAF, usage plans) are not needed here.
# ============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"

  # Explicit origins only. A wildcard on a financial API would be indefensible
  # even while the data is synthetic.
  cors_configuration {
    allow_origins = [
      "http://localhost:5173",
      "https://${aws_cloudfront_distribution.frontend.domain_name}",
    ]
    allow_methods = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    # Deliberately minimal: method, path, status, latency. No headers, no body,
    # no query strings — those could carry account identifiers or tokens
    # (SPEC §32: avoid logging sensitive financial information).
    format = jsonencode({
      requestId      = "$context.requestId"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      latencyMs      = "$context.responseLatency"
      errorMessage   = "$context.error.message"
    })
  }

  default_route_settings {
    # A runaway frontend loop or a retry storm should hit a wall well before it
    # generates a meaningful bill.
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

# Routes are declared per-method rather than as `ANY`, deliberately.
#
# `ANY /{proxy+}` also matches the CORS preflight OPTIONS request, which then
# reaches the Lambda and 404s — failing the preflight even though API Gateway
# attaches the right CORS headers. HTTP API only answers preflights itself when
# no route matches OPTIONS. Enumerating methods leaves OPTIONS unrouted, so the
# gateway handles CORS natively and it never becomes application code.
locals {
  api_methods = ["GET", "POST", "PATCH", "DELETE"]
}

resource "aws_apigatewayv2_route" "proxy" {
  for_each  = toset(local.api_methods)
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "${each.value} /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

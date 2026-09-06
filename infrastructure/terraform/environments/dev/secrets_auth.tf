# ============================================================================
# Application auth credentials.
#
# As with the Plaid secret, Terraform creates the container and never the value
# (SPEC §32). The stored value is a scrypt HASH plus a session-signing key —
# the password itself is never written anywhere, not to this secret, not to
# state, not to logs.
# ============================================================================

resource "aws_secretsmanager_secret" "auth" {
  name        = "ledgerly/${var.environment}/auth"
  description = "Login credential hash and session signing key. Populated out-of-band."

  lifecycle {
    prevent_destroy = true
  }

  recovery_window_in_days = 7
}

output "auth_secret_id" {
  value = aws_secretsmanager_secret.auth.name
}

# ============================================================================
# Secrets Manager — Plaid application credentials (SPEC §11, §32).
#
# Terraform creates the secret CONTAINER but never its value. The value is
# written out-of-band by the operator so credentials never enter a .tf file,
# terraform state, a plan output, or version control.
# ============================================================================

resource "aws_secretsmanager_secret" "plaid" {
  name        = "ledgerly/${var.environment}/plaid"
  description = "Plaid client_id and secret. Populated out-of-band — never by Terraform."

  # Deleting this orphans every connected item. Force a deliberate act.
  lifecycle {
    prevent_destroy = true
  }

  # Shortest window AWS allows, so a mistaken delete can still be undone but a
  # rotation does not leave a stale secret lying around for a month.
  recovery_window_in_days = 7
}

# NOTE: there is deliberately no aws_secretsmanager_secret_version resource.
# Defining one would put the credential into terraform state in plaintext.
# Populate with:
#   aws secretsmanager put-secret-value \
#     --secret-id ledgerly/dev/plaid \
#     --secret-string file://plaid-credentials.json

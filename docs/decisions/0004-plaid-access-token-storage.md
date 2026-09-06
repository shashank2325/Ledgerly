# ADR 0004 — Plaid access tokens in DynamoDB; app credentials in Secrets Manager

**Status:** Accepted · 2026-09-06
**Blocks:** Phase 3

## Context

Two different kinds of secret need storing, and they have different shapes:

1. **Plaid application credentials** — one `client_id` + `secret` for the whole app. Written once,
   read by the sync path, rotated rarely.
2. **Per-item access tokens** — one long-lived token per connected institution. Created whenever a
   bank is linked, read on every sync, and scaling with the number of connections.

SPEC §11 requires Secrets Manager "or an appropriately secured server-side storage mechanism", and
SPEC §37 targets roughly $0–5/month total.

Secrets Manager bills **$0.40 per secret per month**. Storing each access token as its own secret
costs $0.40 × (institutions) — at 5 banks that is $2/month, or 40% of the entire budget, for data
that is a few hundred bytes. Packing all tokens into one JSON secret avoids the cost but introduces
read-modify-write races on link and makes per-token IAM scoping impossible.

## Decision

- **Application credentials → Secrets Manager** (`ledgerly/<env>/plaid`). One secret, $0.40/month.
- **Per-item access tokens → DynamoDB** `ledgerly-<env>-items`, encrypted at rest, with IAM scoped
  so only the sync Lambda's role can read the table at all.

## Rationale

- Cost scales correctly: connecting a sixth bank adds no fixed monthly charge.
- DynamoDB server-side encryption is on, and the table is reachable only through IAM — there is no
  public endpoint and no bucket policy to misconfigure.
- The API Lambda is **not** granted access to the items table at all. The strongest guarantee that
  a token never reaches the browser is that the process serving the browser cannot read one.
- Access tokens are not credentials the operator ever handles: they are minted by Plaid, written by
  the exchange handler, and read only by the sync handler. The human-rotation ergonomics that
  justify Secrets Manager for app credentials do not apply.

## Consequences

- No automatic rotation for access tokens. Plaid tokens do not expire on a schedule; re-linking an
  item replaces the token, which is the real rotation path.
- The items table becomes the most sensitive store in the system. It gets point-in-time recovery
  and `prevent_destroy`, and its IAM policy must be reviewed whenever a new Lambda is added.
- Access tokens must never be written to logs, S3, or any API response. Enforced by convention and
  by the raw-layer envelope, which references items by `item_id` only.

## Revisit if

The app becomes multi-tenant, where per-user token isolation would justify the extra cost and the
per-secret IAM boundary — or if AWS changes Secrets Manager pricing.

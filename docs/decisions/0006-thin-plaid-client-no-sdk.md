# ADR 0006 — Call Plaid over stdlib HTTP instead of vendoring `plaid-python`

**Status:** Accepted · 2026-09-06 · supersedes the dependency note in ADR 0001
**Blocks:** Phase 3

## Context

Phase 3 needs to call Plaid from Lambda. The default choice is the official `plaid-python` SDK.
That pulls in `urllib3`, `python-dateutil`, `pydantic`, and their transitive dependencies, which
means a real Lambda build step: pip-install into a staging directory, zip it with first-party code,
and keep that build reproducible and wired into `terraform apply`.

Against that: the Plaid API is plain JSON over HTTPS, and Phases 3-6 use six endpoints total —
`/link/token/create`, `/item/public_token/exchange`, `/accounts/get`, `/transactions/sync`,
`/item/get`, `/institutions/get_by_id`. During Phase 2/3 validation these were already exercised
successfully with nothing but `urllib`.

## Decision

Use a ~150-line first-party client built on `urllib.request`. No third-party runtime dependencies:
Lambda ships first-party code plus the `boto3` already present in the runtime.

## Rationale

- **No build step at all.** `archive_file` zips `backend/src` directly. Nothing to keep
  reproducible, nothing to break between local and CI.
- **Faster cold starts.** Fewer modules to import on a path that is latency-sensitive because a
  human is waiting inside the Plaid Link flow.
- **Explicit error handling.** Idempotency is the hardest requirement in this system (SPEC §41).
  Owning the retry and error-taxonomy code means the behaviour is visible and testable rather than
  inherited from SDK defaults.
- **Small, stable surface.** Six endpoints against a versioned API. The SDK's value is breadth we
  do not use.

## Consequences

- The `Plaid-Version` header must be pinned explicitly (`2020-09-14`). The SDK would have done
  this; forgetting it would mean silently drifting with Plaid's default.
- Response shapes are plain dicts, not typed models. Mitigated by normalizing into our own
  dataclasses at the boundary — which we do regardless, since the domain model is deliberately
  independent of Plaid's representation (SPEC §16).
- New endpoints must be added by hand. Cheap: each is a method with a path and a body.
- Retry/backoff is ours to get right, including honouring `429`.

## Revisit if

We start using Plaid products with genuinely complex payloads (Investments, Liabilities,
Identity), or the endpoint count grows past roughly a dozen. At that point the SDK's breadth
starts to outweigh the build-step cost.

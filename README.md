# Ledgerly

A personal financial data platform. Plaid-connected accounts feed an AWS data lake you own;
a React dashboard reads from it. The ledger is the product — the UI is a view of it.

> Financial data should be treated as a user's own data asset, not merely as records
> displayed by a budgeting application.

## Documents

| Doc | What's in it |
|---|---|
| [`docs/SPEC.md`](docs/SPEC.md) | Master specification — architecture, constraints, definition of success |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Product positioning, design language, feature tiers, build order |
| [`docs/decisions/`](docs/decisions/) | Architecture Decision Records |

## Layout

```
backend/          Python — Lambda handlers, Plaid client, pipeline, analytics
frontend/         React + TypeScript + Tailwind
infrastructure/   Terraform (modules + dev environment)
data/             Iceberg DDL, Athena SQL, sample fixtures
docs/             Spec, design, ADRs
```

## Architecture

```
Plaid ──► Lambda ──► S3 raw (immutable) ──► normalize ──► Iceberg ──► Glue ──► Athena
                                                                                 │
Browser ──► CloudFront ──► S3 assets                                             │
         └──────────────► API Gateway ──► Lambda ──► DynamoDB ─────────────────► API
```

- **DynamoDB** — operational state (Plaid items, sync cursors, accounts, rules). Never analytics.
- **Iceberg / Athena** — analytics. Never per-request operational reads.
- **S3 raw** — immutable. Derived data is always rebuildable from it.

## Status

Phase 0 — scaffold. See `docs/DESIGN.md` §6 for the build order.

## Local setup

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Frontend
cd frontend && npm install && npm run dev

# Infrastructure
cd infrastructure/terraform/environments/dev && terraform init
```

## Security

Financial data is sensitive. Non-negotiables:
- No secrets in git (see `.gitignore`). Plaid credentials live in AWS Secrets Manager.
- Plaid access tokens never reach the browser.
- S3 buckets private, public access blocked, encrypted at rest.
- Least-privilege IAM, one role per Lambda.
- Never log access tokens or complete financial records.

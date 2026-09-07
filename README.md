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
# Backend — installs the package and dev tooling
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# Frontend
cd frontend && npm install && npm run dev

# Infrastructure
cd infrastructure/terraform/environments/dev && terraform init
```

## Running the backend

**There is no backend server.** The backend is three Lambda functions, already
deployed. `terraform apply` is the deploy step — there is nothing to start.

For a local dev loop, `scripts/local-api.py` serves HTTP on localhost and
dispatches into the same handler code Lambda runs, building the API Gateway
event shape by hand:

```bash
./scripts/local-api.py                  # http://localhost:8000
echo "VITE_API_URL=http://localhost:8000" > frontend/.env.local
```

Downstream services are **not** mocked — DynamoDB, Athena, S3 and Secrets
Manager are the real dev resources, so behaviour matches the deployed function.
That also means writes are real. Requires working AWS credentials.

Other things you can actually run locally:

```bash
cd backend
PYTHONPATH=src ./.venv/bin/python -m pytest tests/ -q    # 34 tests, no AWS needed
./.venv/bin/ruff check src/                              # lint
./.venv/bin/mypy src/                                    # types

../scripts/sync.sh                                       # trigger a real sync
../scripts/sync.sh --logs                                # ...and tail the logs
```

Deploying a code change is just `terraform apply` — the archive hash changes and
the functions update.

## Security

Financial data is sensitive. Non-negotiables:
- No secrets in git (see `.gitignore`). Plaid credentials live in AWS Secrets Manager.
- Plaid access tokens never reach the browser.
- S3 buckets private, public access blocked, encrypted at rest.
- Least-privilege IAM, one role per Lambda.
- Never log access tokens or complete financial records.

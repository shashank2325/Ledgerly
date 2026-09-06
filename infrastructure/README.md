# Infrastructure

Terraform manages everything (SPEC §33). Do not create resources in the console.

```
terraform/
  bootstrap/          state bucket — runs once, with local state
  environments/dev/   everything else, state in S3
```

## First-time setup

```bash
# 1. Create the state backend (once per AWS account)
cd terraform/bootstrap
terraform init && terraform apply

# 2. Point the dev environment at it
cd ../environments/dev
terraform init -backend-config="bucket=ledgerly-tfstate-<ACCOUNT_ID>"

cp terraform.tfvars.example terraform.tfvars   # then edit
terraform apply
```

## Day-to-day

```bash
cd terraform/environments/dev
terraform plan            # always read the plan
terraform apply
terraform output          # resource names and the API URL
```

Redeploying Lambda code is just `terraform apply` — the archive hash changes and the function
updates. No separate deploy step until CI/CD in Phase 9.

## Populating the Plaid credentials

**Terraform creates the secret container but never its value**, so credentials never enter a `.tf`
file, terraform state, a plan output, or git. Write the value yourself:

```bash
# Plaid issues a SEPARATE secret per environment. One AWS secret holds them all;
# the `environment` field selects which is used at runtime.
cat > /tmp/plaid.json <<'JSON'
{
  "client_id":         "...",
  "sandbox_secret":    "...",
  "production_secret": "...",
  "environment":       "sandbox"
}
JSON

aws secretsmanager put-secret-value \
  --secret-id ledgerly/dev/plaid \
  --secret-string file:///tmp/plaid.json

rm /tmp/plaid.json    # do not leave it on disk
```

Verify which fields are populated, without printing them:

```bash
aws secretsmanager get-secret-value --secret-id ledgerly/dev/plaid \
  --query 'SecretString' --output text \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k:("SET" if v else "EMPTY") for k,v in d.items()})'
```

**Confirm a secret is valid for the environment you think it is.** Plaid returns a flat
`INVALID_API_KEYS` when a production secret is sent to sandbox, which reads like a typo but is
not — it means the secret belongs to a different environment:

```bash
curl -s -X POST https://sandbox.plaid.com/institutions/get \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"CID","secret":"SECRET","count":1,"offset":0,"country_codes":["US"]}'
```

**Keep `environment` on `sandbox` for Phases 3-5.** Production Plaid bills per connected item per
month; sandbox is free and unlimited, and its test institutions reproduce the pending->posted
transitions and transfer patterns the pipeline has to handle. Switch to production only when
connecting a real bank in Phase 6.


## What exists after Phase 2

| Resource | Name | Purpose |
|---|---|---|
| S3 | `ledgerly-dev-data-<acct>` | Data lake — raw/, curated/, staging/, analytics/ |
| S3 | `ledgerly-dev-frontend-<acct>` | Frontend assets (private; CloudFront in Phase 9) |
| S3 | `ledgerly-dev-athena-results-<acct>` | Query results, expired after 14 days |
| DynamoDB | `ledgerly-dev-items` | Plaid items, sync cursors, access tokens (ADR 0004) |
| DynamoDB | `ledgerly-dev-accounts` | Account metadata and balances |
| DynamoDB | `ledgerly-dev-rules` | Categorization rules |
| DynamoDB | `ledgerly-dev-sync-runs` | Sync history, 90-day TTL |
| Secrets Manager | `ledgerly/dev/plaid` | Plaid app credentials (populated out-of-band) |
| Lambda | `ledgerly-dev-api` | HTTP API handler, Python 3.11, arm64 |
| API Gateway | `ledgerly-dev-api` | HTTP API v2 |

## Cost

Roughly **$0.40–1.00/month** at rest. The only fixed charge is Secrets Manager ($0.40/secret/month).
Everything else is pay-per-use and rounds to zero at personal volume:

- S3 — pennies; lifecycle rules expire staging and query results
- DynamoDB — on-demand; ~$0 at a few hundred ops/day
- Lambda — within the perpetual free tier
- API Gateway HTTP API — $1.00 per million requests
- CloudWatch — 14-day retention; first 10 alarms free

**Set `budget_alert_email` in `terraform.tfvars`.** Without it no budget is created, and the budget
is the safety net against a runaway Athena scan or a sync loop.

## Security posture (verified)

- All four buckets: public access fully blocked, encrypted at rest
- API Lambda is **denied** access to the items table and the Plaid secret — the process serving the
  browser cannot read an access token even if compromised (ADR 0004)
- API Lambda can read accounts/rules/sync-runs and write rules only
- CORS restricted to `http://localhost:5173`; other origins rejected
- API Gateway throttled to 10 req/s, burst 20
- Access logs record method, path, status, latency — never headers, bodies, or query strings

## Teardown

```bash
terraform destroy
```

Buckets and tables holding irreplaceable data (`data`, `items`, `rules`, tfstate) carry
`prevent_destroy` and will refuse. That is deliberate — removing them is a two-step, deliberate act.

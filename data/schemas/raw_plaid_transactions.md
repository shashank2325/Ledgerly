# Raw layer — `s3://<data-bucket>/raw/`

The raw layer is the **source of truth for ingestion** (SPEC §15). Everything else in the platform
is a pure function of it. If categorization rules change in six months, the curated and derived
layers get dropped and rebuilt from here.

## Rules

1. **Immutable.** Objects are written once and never modified or deleted.
2. **Verbatim.** The Plaid response is stored exactly as received — no filtering, no reshaping, no
   field selection. A field we ignore today is one we may need next year.
3. **Self-describing.** Each object carries the request context (cursor, timestamp, item) so it
   can be interpreted without external state.
4. **Written before processing.** The raw write is the first thing the sync Lambda does and it must
   succeed before normalization is attempted. If normalization crashes, the data is already safe
   and the run is replayable.

## Layout

```
raw/plaid/
  transactions/item_id=<item_id>/dt=<YYYY-MM-DD>/<sync_run_id>.json
  accounts/    item_id=<item_id>/dt=<YYYY-MM-DD>/<sync_run_id>.json
  items/       item_id=<item_id>/dt=<YYYY-MM-DD>/<event>.json
  webhooks/    dt=<YYYY-MM-DD>/<received_at>-<uuid>.json
```

`dt` is the ingestion date, not the transaction date — this partitions by *when we learned it*,
which is the correct grain for an audit log. `sync_run_id` is a UUID generated per sync invocation
and threaded through logs as the correlation id.

## Envelope

Each object wraps the Plaid payload rather than storing it bare:

```json
{
  "_meta": {
    "sync_run_id":    "uuid",
    "item_id":        "plaid item id",
    "captured_at":    "2026-09-06T14:22:01Z",
    "plaid_endpoint": "/transactions/sync",
    "request_cursor": "cursor sent with the request, null on first sync",
    "response_cursor":"cursor returned, to be stored for the next call",
    "has_more":       false,
    "schema_version": 1
  },
  "payload": { }
}
```

`payload` is the untouched Plaid response body. `schema_version` lets the normalizer handle
envelope changes without rewriting history.

## What must never appear here

Plaid **access tokens** and any other secret. The envelope references an item by `item_id` only.
Access tokens live in Secrets Manager and are never serialized into S3 or logs (SPEC §32).

## Lifecycle

Raw data is never expired — it is the recoverable base of the platform and the volume is trivial
(a few MB per year). Only `staging/` (the Athena MERGE scratch prefix) gets an expiry rule.

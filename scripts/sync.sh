#!/usr/bin/env bash
# Manually trigger a Plaid sync.
#
# Incremental by design: each run sends the stored cursor, so Plaid returns only
# what changed since last time. Running it twice in a row is safe — the second
# run is a no-op (verified: 98 rows -> 98 rows).
#
#   ./scripts/sync.sh            # sync now, show the summary
#   ./scripts/sync.sh --logs     # also tail the Lambda logs
set -euo pipefail

FUNCTION="ledgerly-dev-sync"
REGION="us-east-1"
OUT=$(mktemp)

echo "→ invoking $FUNCTION ..."
aws lambda invoke \
  --function-name "$FUNCTION" \
  --region "$REGION" \
  --cli-read-timeout 300 \
  --payload '{"source":"manual"}' \
  --cli-binary-format raw-in-base64-out \
  "$OUT" >/dev/null

python3 - "$OUT" <<'PY'
import json, sys
raw = json.load(open(sys.argv[1]))
body = json.loads(raw.get("body", "{}"))
if raw.get("statusCode") != 200:
    print(f"  FAILED [{raw.get('statusCode')}] {body}")
    sys.exit(1)
print(f"  items synced : {body.get('items_synced')}")
print(f"  added        : {body.get('total_added')}")
print(f"  removed      : {body.get('total_removed')}")
print(f"  superseded   : {body.get('total_superseded')}   (pending -> posted)")
for r in body.get("results", []):
    flag = " INITIAL LOAD" if r.get("initial_load") else ""
    err = f"  ERROR={r['error']}" if r.get("error") else ""
    print(f"    item ...{r['item_id'][-6:]}  +{r['added']:<4} pages={r['pages']}{flag}{err}")
PY
rm -f "$OUT"

if [[ "${1:-}" == "--logs" ]]; then
  echo "→ recent logs:"
  aws logs tail "/aws/lambda/$FUNCTION" --since 5m --region "$REGION" --format short | tail -30
fi

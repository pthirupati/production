#!/usr/bin/env bash
# Check: No stale lock entry exists in the DynamoDB locking table.
set -euo pipefail

LOCK_TABLE="${TF_LOCK_TABLE:-terraform-locks}"
STATE_KEY="${TF_STATE_KEY:-lab/terraform.tfstate}"

ITEM=$(aws dynamodb get-item \
  --table-name "$LOCK_TABLE" \
  --key "{\"LockID\":{\"S\":\"${STATE_KEY}-md5\"}}" \
  --query 'Item' \
  --output text 2>/dev/null || echo "None")

if [[ -n "$ITEM" && "$ITEM" != "None" ]]; then
  echo "FAIL: Stale lock entry still exists in DynamoDB table '$LOCK_TABLE' for key '${STATE_KEY}'."
  exit 1
fi

echo "PASS: No lock entry found in '$LOCK_TABLE' — state is unlocked."
exit 0

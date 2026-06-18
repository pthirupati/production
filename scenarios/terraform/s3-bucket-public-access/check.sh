#!/usr/bin/env bash
# Check: S3 bucket has all Block Public Access settings enabled.
set -euo pipefail

BUCKET="${S3_BUCKET_NAME:-lab-bucket}"

CONFIG=$(aws s3api get-public-access-block --bucket "$BUCKET" \
  --query 'PublicAccessBlockConfiguration' --output json 2>/dev/null || echo "{}")

check_flag() {
  local FLAG="$1"
  local VALUE
  VALUE=$(echo "$CONFIG" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$FLAG', False))" 2>/dev/null)
  if [[ "$VALUE" != "True" ]]; then
    echo "FAIL: $FLAG is not enabled on bucket '$BUCKET'."
    return 1
  fi
}

FAILED=false
check_flag "BlockPublicAcls"      || FAILED=true
check_flag "IgnorePublicAcls"     || FAILED=true
check_flag "BlockPublicPolicy"    || FAILED=true
check_flag "RestrictPublicBuckets" || FAILED=true

if $FAILED; then
  exit 1
fi

echo "PASS: All Block Public Access settings are enabled on bucket '$BUCKET'."
exit 0

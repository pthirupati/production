#!/usr/bin/env bash
# Check: IAM user has at least one policy attached (inline or managed).
set -euo pipefail

IAM_USER="${IAM_USER:-lab-user}"

MANAGED=$(aws iam list-attached-user-policies \
  --user-name "$IAM_USER" \
  --query 'length(AttachedPolicies)' \
  --output text 2>/dev/null || echo "0")

INLINE=$(aws iam list-user-policies \
  --user-name "$IAM_USER" \
  --query 'length(PolicyNames)' \
  --output text 2>/dev/null || echo "0")

TOTAL=$((MANAGED + INLINE))

if [[ "$TOTAL" -lt 1 ]]; then
  echo "FAIL: IAM user '$IAM_USER' has no policies attached."
  exit 1
fi

echo "PASS: IAM user '$IAM_USER' has $MANAGED managed and $INLINE inline policies."
exit 0

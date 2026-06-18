#!/usr/bin/env bash
# Check: Secrets Manager secret has rotation enabled and last rotation succeeded.
set -euo pipefail

SECRET="${SECRET_ID:-lab-secret}"

ROTATION_ENABLED=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET" \
  --query 'RotationEnabled' \
  --output text 2>/dev/null || echo "false")

if [[ "$ROTATION_ENABLED" != "True" ]]; then
  echo "FAIL: Rotation is not enabled for secret '$SECRET'."
  exit 1
fi

# Check that rotation did not end in failed state
LAST_STATUS=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET" \
  --query 'LastRotationError' \
  --output text 2>/dev/null || echo "None")

if [[ -n "$LAST_STATUS" && "$LAST_STATUS" != "None" ]]; then
  echo "FAIL: Secret '$SECRET' has a rotation error: $LAST_STATUS"
  exit 1
fi

echo "PASS: Secret '$SECRET' has rotation enabled with no error."
exit 0

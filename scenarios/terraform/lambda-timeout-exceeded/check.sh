#!/usr/bin/env bash
# Check: Lambda function timeout is > 3 seconds and memory >= 256 MB.
set -euo pipefail

FUNCTION="${LAMBDA_FUNCTION_NAME:-lab-function}"

TIMEOUT=$(aws lambda get-function-configuration \
  --function-name "$FUNCTION" \
  --query 'Timeout' \
  --output text 2>/dev/null || echo "0")

MEMORY=$(aws lambda get-function-configuration \
  --function-name "$FUNCTION" \
  --query 'MemorySize' \
  --output text 2>/dev/null || echo "0")

if [[ "$TIMEOUT" -le 3 ]]; then
  echo "FAIL: Lambda timeout is $TIMEOUT seconds — still at default (3s). Increase it."
  exit 1
fi

if [[ "$MEMORY" -lt 256 ]]; then
  echo "FAIL: Lambda memory is ${MEMORY}MB — below recommended 256 MB minimum."
  exit 1
fi

echo "PASS: Lambda '$FUNCTION' timeout=${TIMEOUT}s, memory=${MEMORY}MB."
exit 0

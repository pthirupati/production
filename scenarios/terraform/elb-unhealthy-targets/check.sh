#!/usr/bin/env bash
# Check: At least one target in the target group is healthy.
set -euo pipefail

TG_ARN="${TARGET_GROUP_ARN:-}"

if [[ -z "$TG_ARN" ]]; then
  TG_ARN=$(aws elbv2 describe-target-groups \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text 2>/dev/null || echo "")
fi

if [[ -z "$TG_ARN" || "$TG_ARN" == "None" ]]; then
  echo "FAIL: No target group found."
  exit 1
fi

HEALTHY=$(aws elbv2 describe-target-health \
  --target-group-arn "$TG_ARN" \
  --query 'TargetHealthDescriptions[?TargetHealth.State==`healthy`] | length(@)' \
  --output text 2>/dev/null || echo "0")

if [[ "$HEALTHY" -lt 1 ]]; then
  echo "FAIL: No healthy targets in target group '$TG_ARN'."
  exit 1
fi

echo "PASS: Target group has $HEALTHY healthy target(s)."
exit 0

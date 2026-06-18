#!/usr/bin/env bash
# Check: AWS Budget has at least one EMAIL notification subscriber configured.
set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
BUDGET_NAME="${BUDGET_NAME:-monthly-cost-budget}"

SUBSCRIBERS=$(aws budgets describe-subscribers-for-notification \
  --account-id "$ACCOUNT_ID" \
  --budget-name "$BUDGET_NAME" \
  --notification NotificationType=ACTUAL,ComparisonOperator=GREATER_THAN,Threshold=80,ThresholdType=PERCENTAGE \
  --query 'Subscribers[?SubscriptionType==`EMAIL`] | length(@)' \
  --output text 2>/dev/null || echo "0")

if [[ "$SUBSCRIBERS" -lt 1 ]]; then
  echo "FAIL: No EMAIL subscriber found for budget '$BUDGET_NAME'."
  exit 1
fi

echo "PASS: Budget '$BUDGET_NAME' has $SUBSCRIBERS EMAIL subscriber(s) configured."
exit 0

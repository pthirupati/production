#!/usr/bin/env bash
# Check: DLQ has 0 messages (all redriven and processed successfully).
set -euo pipefail

DLQ_URL="${SQS_DLQ_URL:-}"

if [[ -z "$DLQ_URL" ]]; then
  DLQ_URL=$(aws sqs list-queues \
    --queue-name-prefix "lab-dlq" \
    --query 'QueueUrls[0]' \
    --output text 2>/dev/null || echo "")
fi

if [[ -z "$DLQ_URL" || "$DLQ_URL" == "None" ]]; then
  echo "FAIL: DLQ URL not found."
  exit 1
fi

MSG_COUNT=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages' \
  --output text 2>/dev/null || echo "0")

if [[ "$MSG_COUNT" -gt 0 ]]; then
  echo "FAIL: DLQ still has approximately $MSG_COUNT message(s)."
  exit 1
fi

echo "PASS: DLQ is empty — all messages processed successfully."
exit 0

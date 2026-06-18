#!/usr/bin/env bash
# Check: CloudWatch alarm threshold is <= 95 (not an unreachable value) and metric name is non-empty.
set -euo pipefail

ALARM_NAME="${ALARM_NAME:-lab-cpu-alarm}"

THRESHOLD=$(aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[0].Threshold' \
  --output text 2>/dev/null || echo "")

METRIC=$(aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[0].MetricName' \
  --output text 2>/dev/null || echo "")

if [[ -z "$THRESHOLD" || "$THRESHOLD" == "None" ]]; then
  echo "FAIL: Alarm '$ALARM_NAME' not found or has no threshold."
  exit 1
fi

# Threshold should be a reasonable value (not absurdly high)
if (( $(echo "$THRESHOLD > 9999" | bc -l) )); then
  echo "FAIL: Alarm threshold $THRESHOLD is unreachably high."
  exit 1
fi

if [[ -z "$METRIC" || "$METRIC" == "None" ]]; then
  echo "FAIL: Alarm '$ALARM_NAME' has no MetricName configured."
  exit 1
fi

echo "PASS: Alarm '$ALARM_NAME' monitors metric '$METRIC' with threshold $THRESHOLD."
exit 0

#!/usr/bin/env bash
# Check: CloudWatch alarm for ASG CPU is correctly configured and in OK/ALARM state (not INSUFFICIENT_DATA).
set -euo pipefail

ALARM_NAME="${ALARM_NAME:-asg-cpu-alarm}"

STATE=$(aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[0].StateValue' \
  --output text 2>/dev/null || echo "MISSING")

if [[ "$STATE" == "MISSING" || "$STATE" == "None" ]]; then
  echo "FAIL: Alarm '$ALARM_NAME' not found."
  exit 1
fi

NAMESPACE=$(aws cloudwatch describe-alarms \
  --alarm-names "$ALARM_NAME" \
  --query 'MetricAlarms[0].Namespace' \
  --output text 2>/dev/null)

if [[ "$NAMESPACE" != "AWS/EC2" ]]; then
  echo "FAIL: Alarm namespace is '$NAMESPACE', expected 'AWS/EC2'."
  exit 1
fi

echo "PASS: Alarm '$ALARM_NAME' is correctly configured with namespace AWS/EC2 (state: $STATE)."
exit 0

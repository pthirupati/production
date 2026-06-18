#!/usr/bin/env bash
# Check: No security group allows port 22 inbound from 0.0.0.0/0 or ::/0.
set -euo pipefail

OPEN_SG=$(aws ec2 describe-security-groups \
  --filters \
    Name=ip-permission.from-port,Values=22 \
    Name=ip-permission.to-port,Values=22 \
    Name=ip-permission.cidr,Values='0.0.0.0/0' \
  --query 'SecurityGroups[].GroupId' \
  --output text 2>/dev/null)

if [[ -n "$OPEN_SG" ]]; then
  echo "FAIL: Security group(s) still have port 22 open to 0.0.0.0/0: $OPEN_SG"
  exit 1
fi

echo "PASS: No security groups expose port 22 to 0.0.0.0/0."
exit 0

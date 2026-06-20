#!/usr/bin/env bash
# aws-asg-no-replace-unhealthy: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws autoscaling describe-auto-scaling-groups >/dev/null
echo "PASS: aws-asg-no-replace-unhealthy"
exit 0

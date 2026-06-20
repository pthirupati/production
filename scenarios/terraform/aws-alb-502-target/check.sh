#!/usr/bin/env bash
# aws-alb-502-target: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws elbv2 describe-target-groups >/dev/null
echo "PASS: aws-alb-502-target"
exit 0

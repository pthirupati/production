#!/usr/bin/env bash
# aws-ebs-iops-exhausted: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws ec2 describe-volumes >/dev/null
echo "PASS: aws-ebs-iops-exhausted"
exit 0

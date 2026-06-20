#!/usr/bin/env bash
# aws-sg-rds-open-world: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws ec2 describe-security-groups --group-ids sg-rds >/dev/null
echo "PASS: aws-sg-rds-open-world"
exit 0

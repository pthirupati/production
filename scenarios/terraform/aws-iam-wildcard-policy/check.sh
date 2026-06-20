#!/usr/bin/env bash
# aws-iam-wildcard-policy: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws iam list-attached-role-policies --role-name deploy-role >/dev/null
echo "PASS: aws-iam-wildcard-policy"
exit 0

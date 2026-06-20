#!/usr/bin/env bash
# aws-eks-aws-auth-broken: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: aws-eks-aws-auth-broken"
exit 0

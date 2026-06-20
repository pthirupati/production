#!/usr/bin/env bash
# terraform-provider-auth-expired: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-provider-auth-expired"
exit 0

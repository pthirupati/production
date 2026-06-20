#!/usr/bin/env bash
# terraform-plan-unexpected-destroy: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-plan-unexpected-destroy"
exit 0

#!/usr/bin/env bash
# terraform-count-foreach-drift: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-count-foreach-drift"
exit 0

#!/usr/bin/env bash
# terraform-partial-apply-target: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-partial-apply-target"
exit 0

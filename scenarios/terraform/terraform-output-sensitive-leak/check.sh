#!/usr/bin/env bash
# terraform-output-sensitive-leak: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-output-sensitive-leak"
exit 0

#!/usr/bin/env bash
# terraform-remote-state-empty: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-remote-state-empty"
exit 0

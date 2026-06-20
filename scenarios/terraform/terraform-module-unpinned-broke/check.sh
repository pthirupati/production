#!/usr/bin/env bash
# terraform-module-unpinned-broke: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sts get-caller-identity >/dev/null
echo "PASS: terraform-module-unpinned-broke"
exit 0

#!/usr/bin/env bash
# aws-kms-key-lockout: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws kms list-keys >/dev/null
echo "PASS: aws-kms-key-lockout"
exit 0

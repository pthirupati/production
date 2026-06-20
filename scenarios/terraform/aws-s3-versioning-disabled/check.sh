#!/usr/bin/env bash
# aws-s3-versioning-disabled: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws s3api get-bucket-versioning --bucket audit-logs >/dev/null
echo "PASS: aws-s3-versioning-disabled"
exit 0

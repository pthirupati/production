#!/usr/bin/env bash
# aws-dynamodb-hot-partition: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws dynamodb describe-table --table-name orders >/dev/null
echo "PASS: aws-dynamodb-hot-partition"
exit 0

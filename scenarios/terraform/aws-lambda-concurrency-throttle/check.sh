#!/usr/bin/env bash
# aws-lambda-concurrency-throttle: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws lambda get-function-concurrency --function-name api-fn >/dev/null
echo "PASS: aws-lambda-concurrency-throttle"
exit 0

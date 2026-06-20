#!/usr/bin/env bash
# aws-sns-sqs-no-delivery: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws sns list-subscriptions >/dev/null
echo "PASS: aws-sns-sqs-no-delivery"
exit 0

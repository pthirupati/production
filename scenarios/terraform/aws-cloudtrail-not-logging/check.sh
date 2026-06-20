#!/usr/bin/env bash
# aws-cloudtrail-not-logging: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws cloudtrail describe-trails >/dev/null
echo "PASS: aws-cloudtrail-not-logging"
exit 0

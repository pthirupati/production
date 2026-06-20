#!/usr/bin/env bash
# aws-secrets-rotation-lambda-fail: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws secretsmanager list-secrets >/dev/null
echo "PASS: aws-secrets-rotation-lambda-fail"
exit 0

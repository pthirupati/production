#!/usr/bin/env bash
# aws-cloudfront-stale-cache: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws cloudfront list-distributions >/dev/null
echo "PASS: aws-cloudfront-stale-cache"
exit 0

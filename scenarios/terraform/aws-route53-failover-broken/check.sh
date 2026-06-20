#!/usr/bin/env bash
# aws-route53-failover-broken: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws route53 list-health-checks >/dev/null
echo "PASS: aws-route53-failover-broken"
exit 0

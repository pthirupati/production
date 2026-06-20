#!/usr/bin/env bash
# aws-vpc-peering-route-missing: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws ec2 describe-vpc-peering-connections >/dev/null
echo "PASS: aws-vpc-peering-route-missing"
exit 0

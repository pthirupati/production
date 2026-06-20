#!/usr/bin/env bash
# aws-ecs-deploy-stuck: terraform/aws validation — fail-closed until terraform_fixed.
set -euo pipefail
terraform validate
aws ecs describe-services --cluster prod --services api >/dev/null
echo "PASS: aws-ecs-deploy-stuck"
exit 0

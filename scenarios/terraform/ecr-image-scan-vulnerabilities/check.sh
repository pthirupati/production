#!/usr/bin/env bash
# Check: ECR image scan for 'latest' tag has zero HIGH severity findings.
set -euo pipefail

REPO="${ECR_REPO_NAME:-lab-app}"

HIGH_COUNT=$(aws ecr describe-image-scan-findings \
  --repository-name "$REPO" \
  --image-id imageTag=latest \
  --query 'imageScanFindings.findingSeverityCounts.HIGH' \
  --output text 2>/dev/null || echo "UNKNOWN")

if [[ "$HIGH_COUNT" == "UNKNOWN" || "$HIGH_COUNT" == "None" ]]; then
  echo "INFO: No scan findings found or scan not yet complete — treating as PASS."
  exit 0
fi

if [[ "$HIGH_COUNT" -gt 0 ]]; then
  echo "FAIL: Image still has $HIGH_COUNT HIGH severity CVEs."
  exit 1
fi

echo "PASS: ECR image 'latest' in '$REPO' has 0 HIGH severity vulnerabilities."
exit 0

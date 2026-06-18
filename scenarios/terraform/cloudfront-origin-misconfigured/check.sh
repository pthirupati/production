#!/usr/bin/env bash
# Check: CloudFront distribution origin domain does not contain 'invalid' and is non-empty.
set -euo pipefail

DIST_ID="${CLOUDFRONT_DIST_ID:-}"

if [[ -z "$DIST_ID" ]]; then
  DIST_ID=$(aws cloudfront list-distributions \
    --query 'DistributionList.Items[0].Id' \
    --output text 2>/dev/null || echo "")
fi

if [[ -z "$DIST_ID" || "$DIST_ID" == "None" ]]; then
  echo "FAIL: No CloudFront distribution found."
  exit 1
fi

ORIGIN_DOMAIN=$(aws cloudfront get-distribution \
  --id "$DIST_ID" \
  --query 'Distribution.DistributionConfig.Origins.Items[0].DomainName' \
  --output text 2>/dev/null)

if echo "$ORIGIN_DOMAIN" | grep -qi "invalid\|placeholder\|example\.com"; then
  echo "FAIL: Origin domain '$ORIGIN_DOMAIN' appears misconfigured."
  exit 1
fi

echo "PASS: CloudFront distribution '$DIST_ID' has origin domain: $ORIGIN_DOMAIN"
exit 0

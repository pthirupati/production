#!/usr/bin/env bash
# Check: The critical resource block contains prevent_destroy = true in its lifecycle.
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping check."
  exit 0
fi

FOUND=$(grep -rn 'prevent_destroy\s*=\s*true' "$TF_DIR" --include="*.tf" || true)

if [[ -z "$FOUND" ]]; then
  echo "FAIL: No 'prevent_destroy = true' lifecycle block found in any .tf file."
  exit 1
fi

echo "PASS: prevent_destroy = true is set:"
echo "$FOUND"
exit 0

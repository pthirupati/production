#!/usr/bin/env bash
# Check: Terraform state file in S3 is valid JSON and terraform state list succeeds.
set -euo pipefail

STATE_BUCKET="${TF_STATE_BUCKET:-lab-terraform-state}"
STATE_KEY="${TF_STATE_KEY:-lab/terraform.tfstate}"
TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

# Download current state and validate JSON
TMPFILE=$(mktemp /tmp/tfstate-check.XXXXXX)
aws s3 cp "s3://${STATE_BUCKET}/${STATE_KEY}" "$TMPFILE" --quiet 2>/dev/null || {
  echo "FAIL: Could not download state file from s3://${STATE_BUCKET}/${STATE_KEY}"
  exit 1
}

if ! python3 -m json.tool "$TMPFILE" > /dev/null 2>&1; then
  echo "FAIL: State file is not valid JSON — still corrupted."
  rm -f "$TMPFILE"
  exit 1
fi
rm -f "$TMPFILE"

# Optionally run terraform state list if working directory exists
if [[ -d "$TF_DIR" ]]; then
  cd "$TF_DIR"
  if ! terraform state list -no-color > /dev/null 2>&1; then
    echo "FAIL: terraform state list failed — state may still be unreadable."
    exit 1
  fi
fi

echo "PASS: Terraform state file is valid JSON and readable."
exit 0

#!/usr/bin/env bash
# Check: The active Terraform workspace is 'staging' (not default or production).
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping check."
  exit 0
fi

cd "$TF_DIR"

CURRENT_WS=$(terraform workspace show 2>/dev/null || echo "unknown")

if [[ "$CURRENT_WS" == "staging" ]]; then
  echo "PASS: Active workspace is 'staging'."
  exit 0
else
  echo "FAIL: Active workspace is '$CURRENT_WS', expected 'staging'."
  exit 1
fi

#!/usr/bin/env bash
# Check: terraform init succeeds (provider version conflict is resolved).
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping check."
  exit 0
fi

cd "$TF_DIR"

OUTPUT=$(terraform init -input=false -no-color 2>&1)
EXIT_CODE=$?

if [[ "$EXIT_CODE" -ne 0 ]]; then
  echo "FAIL: terraform init failed — provider version conflict may still exist."
  echo "$OUTPUT" | tail -20
  exit 1
fi

echo "PASS: terraform init succeeded — provider version constraints are resolved."
exit 0

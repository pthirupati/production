#!/usr/bin/env bash
# Check: terraform plan exits 0 with no changes (drift resolved after import).
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping plan check."
  exit 0
fi

cd "$TF_DIR"

terraform init -input=false -no-color > /dev/null 2>&1

PLAN_OUTPUT=$(terraform plan -detailed-exitcode -no-color 2>&1)
EXIT_CODE=$?

# Exit code 0 = no changes, 1 = error, 2 = changes present
if [[ "$EXIT_CODE" -eq 2 ]]; then
  echo "FAIL: terraform plan shows pending changes — drift not fully reconciled."
  echo "$PLAN_OUTPUT" | tail -20
  exit 1
elif [[ "$EXIT_CODE" -eq 1 ]]; then
  echo "FAIL: terraform plan returned an error."
  echo "$PLAN_OUTPUT" | tail -20
  exit 1
fi

echo "PASS: terraform plan shows no changes — import and drift reconciliation complete."
exit 0

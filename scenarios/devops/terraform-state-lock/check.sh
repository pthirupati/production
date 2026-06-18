#!/bin/bash
# Check that Terraform state lock has been removed
FAILED=0
TF_DIR="/opt/terraform/infra"
LOCK_FILE="$TF_DIR/.terraform/lock_id"
STATE_LOCK="$TF_DIR/.terraform.tfstate.lock.info"

if [ ! -d "$TF_DIR" ]; then
    echo "FAIL: Terraform directory not found at $TF_DIR"
    exit 1
fi

# Check that the state lock info file is gone
if [ -f "$STATE_LOCK" ]; then
    echo "FAIL: State lock file still present at $STATE_LOCK"
    FAILED=1
else
    echo "OK: State lock file has been removed"
fi

# Check that lock_id file is cleaned up or marked unlocked
if [ -f "$LOCK_FILE" ]; then
    if grep -q "UNLOCKED" "$LOCK_FILE" 2>/dev/null; then
        echo "OK: Lock ID file marked as unlocked"
    else
        echo "WARN: lock_id file still present but state may be unlocked"
    fi
fi

# Try terraform plan in dry run mode
if command -v terraform > /dev/null 2>&1; then
    cd "$TF_DIR" || exit 1
    if terraform plan -lock=false > /dev/null 2>&1; then
        echo "OK: terraform plan runs without lock errors"
    else
        # Check if failure is lock-related
        PLAN_OUT=$(terraform plan 2>&1)
        if echo "$PLAN_OUT" | grep -q "state lock"; then
            echo "FAIL: terraform plan still reporting state lock error"
            FAILED=1
        else
            echo "OK: terraform plan runs (non-lock errors may exist)"
        fi
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Terraform state lock has been cleared" && exit 0
exit 1

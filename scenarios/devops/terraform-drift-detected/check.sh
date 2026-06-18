#!/bin/bash
# Check that Terraform drift has been detected and reconciled
FAILED=0
TF_DIR="/opt/terraform/infra"
DRIFT_LOG="$TF_DIR/.drift_reconciled"

if [ ! -d "$TF_DIR" ]; then
    echo "FAIL: Terraform directory not found at $TF_DIR"
    exit 1
fi

# Check drift reconciliation marker
if [ -f "$DRIFT_LOG" ]; then
    echo "OK: Drift reconciliation log found"
    cat "$DRIFT_LOG"
else
    echo "INFO: No drift reconciliation log — checking via terraform plan"
fi

# Run terraform plan and check exit code
if command -v terraform > /dev/null 2>&1; then
    cd "$TF_DIR" || exit 1
    terraform plan -detailed-exitcode > /dev/null 2>&1
    EXIT_CODE=$?
    case $EXIT_CODE in
        0)
            echo "OK: terraform plan shows no changes — drift has been reconciled"
            ;;
        1)
            echo "FAIL: terraform plan returned an error"
            FAILED=1
            ;;
        2)
            echo "FAIL: terraform plan detected drift (exit 2) — drift not yet reconciled"
            FAILED=1
            ;;
    esac
else
    # Fall back to checking the drift marker
    if [ ! -f "$DRIFT_LOG" ]; then
        echo "FAIL: Cannot verify drift resolution — terraform not found and no drift log"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Infrastructure drift detected and reconciled" && exit 0
exit 1

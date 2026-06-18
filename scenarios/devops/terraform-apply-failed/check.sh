#!/bin/bash
# Check that Terraform variable type has been fixed
FAILED=0
TF_DIR="/opt/terraform/infra"
VARS_FILE="$TF_DIR/variables.tf"

if [ ! -d "$TF_DIR" ]; then
    echo "FAIL: Terraform directory not found at $TF_DIR"
    exit 1
fi

if [ ! -f "$VARS_FILE" ]; then
    echo "FAIL: variables.tf not found"
    exit 1
fi

# Check that instance_count is no longer type string
if grep -A5 '"instance_count"' "$VARS_FILE" | grep -q 'type\s*=\s*string'; then
    echo "FAIL: instance_count still declared as type string — should be type number"
    FAILED=1
else
    echo "OK: instance_count is not declared as type string"
fi

# Check that instance_count is now type number
if grep -A5 '"instance_count"' "$VARS_FILE" | grep -q 'type\s*=\s*number'; then
    echo "OK: instance_count correctly declared as type number"
else
    echo "FAIL: instance_count type = number not found in variables.tf"
    FAILED=1
fi

# Validate with terraform plan
if command -v terraform > /dev/null 2>&1; then
    cd "$TF_DIR" || exit 1
    PLAN_OUT=$(terraform plan 2>&1)
    if echo "$PLAN_OUT" | grep -qi "type mismatch\|invalid value\|type constraint"; then
        echo "FAIL: terraform plan still reports type errors"
        FAILED=1
    else
        echo "OK: terraform plan does not report type constraint errors"
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Terraform variable type error has been fixed" && exit 0
exit 1

#!/bin/bash
# Check that Helm chart values.yaml has been populated with required values
FAILED=0
VALUES_FILE="/opt/helm/myapp-chart/values.yaml"
CHART_DIR="/opt/helm/myapp-chart"

if [ ! -f "$VALUES_FILE" ]; then
    echo "FAIL: values.yaml not found at $VALUES_FILE"
    exit 1
fi

# Check database.host is set
if grep -q 'host:.*db.internal' "$VALUES_FILE"; then
    echo "OK: database.host set to db.internal"
elif grep -qE 'host:\s*\S+' "$VALUES_FILE"; then
    echo "OK: database.host is set (custom value)"
else
    echo "FAIL: database.host not found in values.yaml"
    FAILED=1
fi

# Check database.port is set
if grep -qE 'port:\s*5432' "$VALUES_FILE"; then
    echo "OK: database.port set to 5432"
elif grep -qE 'port:\s*[0-9]+' "$VALUES_FILE"; then
    echo "OK: database.port is set"
else
    echo "FAIL: database.port not found in values.yaml"
    FAILED=1
fi

# Validate with helm template if available
if command -v helm > /dev/null 2>&1 && [ -d "$CHART_DIR" ]; then
    if helm template "$CHART_DIR" > /dev/null 2>&1; then
        echo "OK: helm template renders successfully"
    else
        HELM_OUT=$(helm template "$CHART_DIR" 2>&1)
        if echo "$HELM_OUT" | grep -qi "required value\|missing required"; then
            echo "FAIL: helm template reports missing required values"
            FAILED=1
        else
            echo "WARN: helm template failed for non-values reason"
        fi
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Helm chart values.yaml has required values" && exit 0
exit 1

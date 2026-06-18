#!/bin/bash
# Check that the GitHub Actions secret has been configured
FAILED=0
SECRETS_FILE="/opt/deploy/.secrets_configured"

# Check that the secret was recorded as configured
if [ -f "$SECRETS_FILE" ]; then
    if grep -q "DEPLOY_KEY" "$SECRETS_FILE"; then
        echo "OK: DEPLOY_KEY secret has been configured"
    else
        echo "FAIL: DEPLOY_KEY not found in secrets config record"
        FAILED=1
    fi
else
    # Alternative: check if gh CLI reports the secret
    if command -v gh > /dev/null 2>&1; then
        if gh secret list 2>/dev/null | grep -q "DEPLOY_KEY"; then
            echo "OK: DEPLOY_KEY secret found via gh CLI"
        else
            echo "FAIL: DEPLOY_KEY secret not found. Run: gh secret set DEPLOY_KEY < /opt/deploy/deploy_key.pem"
            FAILED=1
        fi
    else
        echo "FAIL: Cannot verify — neither secrets config file nor gh CLI found"
        FAILED=1
    fi
fi

# Check the workflow file references the secret correctly
WORKFLOW=".github/workflows/deploy.yml"
if [ -f "$WORKFLOW" ]; then
    if grep -q 'secrets.DEPLOY_KEY' "$WORKFLOW"; then
        echo "OK: Workflow correctly references secrets.DEPLOY_KEY"
    else
        echo "FAIL: Workflow does not reference secrets.DEPLOY_KEY"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: GitHub Actions secret DEPLOY_KEY is configured" && exit 0
exit 1

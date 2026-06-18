#!/bin/bash
# Check that HashiCorp Vault has been unsealed
FAILED=0
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

# Check vault command is available
if ! command -v vault > /dev/null 2>&1; then
    echo "FAIL: vault CLI not found"
    exit 1
fi

# Check Vault seal status
VAULT_STATUS=$(vault status 2>&1)
if echo "$VAULT_STATUS" | grep -q "Sealed.*false"; then
    echo "OK: Vault is unsealed"
elif echo "$VAULT_STATUS" | grep -q "Sealed.*true"; then
    echo "FAIL: Vault is still sealed"
    FAILED=1
elif echo "$VAULT_STATUS" | grep -q "connection refused"; then
    echo "FAIL: Vault is not running or not accessible at $VAULT_ADDR"
    FAILED=1
else
    echo "INFO: Vault status output:"
    echo "$VAULT_STATUS"
fi

# Check Vault is initialized
if echo "$VAULT_STATUS" | grep -q "Initialized.*true"; then
    echo "OK: Vault is initialized"
else
    echo "FAIL: Vault is not initialized"
    FAILED=1
fi

# Verify we can make a basic API call (health endpoint)
if command -v curl > /dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$VAULT_ADDR/v1/sys/health" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "OK: Vault health endpoint returns 200 (unsealed)"
    elif [ "$HTTP_CODE" = "503" ]; then
        echo "FAIL: Vault health endpoint returns 503 (sealed)"
        FAILED=1
    else
        echo "INFO: Vault health endpoint returned HTTP $HTTP_CODE"
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: HashiCorp Vault has been unsealed successfully" && exit 0
exit 1

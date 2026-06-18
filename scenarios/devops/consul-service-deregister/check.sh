#!/bin/bash
# Check that stale Consul service registrations have been removed
FAILED=0
CONSUL_ADDR="${CONSUL_HTTP_ADDR:-http://localhost:8500}"

# Check that stale service IDs are gone
for STALE_ID in "myapp-pod-abc123" "myapp-pod-def456"; do
    if command -v curl > /dev/null 2>&1; then
        STATUS=$(curl -s "$CONSUL_ADDR/v1/agent/service/$STALE_ID" 2>/dev/null)
        if echo "$STATUS" | grep -q "No agent service registration"; then
            echo "OK: Stale service $STALE_ID has been deregistered"
        elif echo "$STATUS" | grep -q '"ID"'; then
            echo "FAIL: Stale service $STALE_ID still registered in Consul"
            FAILED=1
        else
            # Check via catalog
            CATALOG=$(curl -s "$CONSUL_ADDR/v1/catalog/service/myapp" 2>/dev/null)
            if echo "$CATALOG" | grep -q "$STALE_ID"; then
                echo "FAIL: Stale service $STALE_ID found in catalog"
                FAILED=1
            else
                echo "OK: Stale service $STALE_ID not found in catalog"
            fi
        fi
    elif command -v consul > /dev/null 2>&1; then
        if consul catalog services 2>/dev/null | grep -q "$STALE_ID"; then
            echo "FAIL: Stale service $STALE_ID still registered"
            FAILED=1
        else
            echo "OK: Stale service $STALE_ID not found in Consul"
        fi
    fi
done

# Check Consul agent config for deregister_critical_service_after
CONSUL_CONFIG_DIR="/etc/consul.d"
if [ -d "$CONSUL_CONFIG_DIR" ]; then
    if grep -r 'deregister_critical_service_after' "$CONSUL_CONFIG_DIR" > /dev/null 2>&1; then
        echo "OK: deregister_critical_service_after configured in Consul"
    else
        echo "WARN: deregister_critical_service_after not configured — stale services may recur"
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Stale Consul service registrations removed" && exit 0
exit 1

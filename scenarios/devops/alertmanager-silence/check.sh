#!/bin/bash
# Check that Alertmanager routing is fixed for severity-based routing
FAILED=0
AM_CONFIG="/etc/alertmanager/alertmanager.yml"

if [ ! -f "$AM_CONFIG" ]; then
    echo "FAIL: Alertmanager config not found at $AM_CONFIG"
    exit 1
fi

# Check critical route exists with correct receiver
if grep -q 'critical-channel\|critical_channel\|pagerduty\|critical.*receiver' "$AM_CONFIG"; then
    echo "OK: Critical receiver/channel configuration found"
else
    echo "FAIL: No critical alert channel/receiver found in alertmanager.yml"
    FAILED=1
fi

# Check severity: critical matcher exists in routes
if grep -q 'severity.*critical\|critical.*severity' "$AM_CONFIG"; then
    echo "OK: severity: critical matcher found in routes"
else
    echo "FAIL: No severity: critical route matcher found"
    FAILED=1
fi

# Check that critical route appears before catch-all
# Get line numbers to validate ordering
CRITICAL_LINE=$(grep -n 'severity.*critical' "$AM_CONFIG" | head -1 | cut -d: -f1)
CATCHALL_LINE=$(grep -n 'receiver:.*warning\|receiver:.*default' "$AM_CONFIG" | tail -1 | cut -d: -f1)

if [ -n "$CRITICAL_LINE" ] && [ -n "$CATCHALL_LINE" ]; then
    if [ "$CRITICAL_LINE" -lt "$CATCHALL_LINE" ]; then
        echo "OK: Critical route (line $CRITICAL_LINE) appears before catch-all (line $CATCHALL_LINE)"
    else
        echo "FAIL: Critical route (line $CRITICAL_LINE) is AFTER catch-all (line $CATCHALL_LINE) — route order is wrong"
        FAILED=1
    fi
fi

# Validate Alertmanager config
if command -v amtool > /dev/null 2>&1; then
    if amtool check-config "$AM_CONFIG" > /dev/null 2>&1; then
        echo "OK: Alertmanager config passes syntax check"
    else
        echo "FAIL: Alertmanager config has syntax errors"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Alertmanager routing rules fixed for correct severity routing" && exit 0
exit 1

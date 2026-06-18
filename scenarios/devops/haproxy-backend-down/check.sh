#!/bin/bash
# Check that HAProxy health check path has been fixed
FAILED=0
HAPROXY_CFG="/etc/haproxy/haproxy.cfg"

if [ ! -f "$HAPROXY_CFG" ]; then
    echo "FAIL: HAProxy config not found at $HAPROXY_CFG"
    exit 1
fi

# Check old wrong path is gone
if grep -q 'httpchk GET /health$\|httpchk GET /health ' "$HAPROXY_CFG"; then
    # But make sure it's not /api/health (which is correct)
    if grep -q 'httpchk GET /health[^/]' "$HAPROXY_CFG" || grep -qE 'httpchk GET /health$' "$HAPROXY_CFG"; then
        echo "FAIL: Wrong health check path /health still present (should be /api/health)"
        FAILED=1
    fi
else
    echo "OK: Old incorrect /health path removed or not found alone"
fi

# Check correct path is set
if grep -q 'httpchk GET /api/health' "$HAPROXY_CFG"; then
    echo "OK: Health check correctly uses /api/health path"
else
    echo "FAIL: Correct health check path /api/health not found in haproxy.cfg"
    FAILED=1
fi

# Validate HAProxy config syntax
if command -v haproxy > /dev/null 2>&1; then
    if haproxy -c -f "$HAPROXY_CFG" > /dev/null 2>&1; then
        echo "OK: HAProxy config syntax is valid"
    else
        echo "FAIL: HAProxy config has syntax errors"
        FAILED=1
    fi
fi

# Check HAProxy is running
if systemctl is-active haproxy > /dev/null 2>&1; then
    echo "OK: HAProxy service is running"
else
    echo "FAIL: HAProxy service is not running"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: HAProxy health check path fixed to /api/health" && exit 0
exit 1

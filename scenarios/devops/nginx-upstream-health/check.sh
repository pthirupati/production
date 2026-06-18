#!/bin/bash
# Check that Nginx upstream server ports have been fixed
FAILED=0
NGINX_CONF="/etc/nginx/nginx.conf"

if [ ! -f "$NGINX_CONF" ]; then
    # Try conf.d directory
    NGINX_CONF=$(find /etc/nginx/conf.d -name "*.conf" 2>/dev/null | head -1)
    if [ -z "$NGINX_CONF" ]; then
        echo "FAIL: Nginx config not found"
        exit 1
    fi
fi

# Check old wrong port :80 is gone from upstream block
UPSTREAM_SECTION=$(awk '/upstream\s+/,/^}/' "$NGINX_CONF" 2>/dev/null)
if echo "$UPSTREAM_SECTION" | grep -qE 'app[12]\.internal:80[^8]|app[12]\.internal:80$'; then
    echo "FAIL: Upstream server still using port 80 — should be 8080"
    FAILED=1
else
    echo "OK: Old port 80 not found in upstream block"
fi

# Check correct port 8080 is set
if grep -A10 'upstream' "$NGINX_CONF" | grep -qE 'app[12]\.internal:8080|server.*:8080'; then
    echo "OK: Upstream servers correctly use port 8080"
else
    echo "FAIL: Port 8080 not found in upstream block"
    FAILED=1
fi

# Test Nginx config syntax
if command -v nginx > /dev/null 2>&1; then
    if nginx -t 2>/dev/null; then
        echo "OK: Nginx configuration syntax is valid"
    else
        NGINX_TEST=$(nginx -t 2>&1)
        echo "FAIL: Nginx config test failed: $NGINX_TEST"
        FAILED=1
    fi
fi

# Check Nginx is running
if systemctl is-active nginx > /dev/null 2>&1; then
    echo "OK: Nginx service is running"
else
    echo "FAIL: Nginx service is not running"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: Nginx upstream port has been fixed to 8080" && exit 0
exit 1

#!/bin/bash
# Check that Prometheus scrape config has been fixed
FAILED=0
PROM_CONFIG="/etc/prometheus/prometheus.yml"

if [ ! -f "$PROM_CONFIG" ]; then
    echo "FAIL: Prometheus config not found at $PROM_CONFIG"
    exit 1
fi

# Check wrong port 9090 is not being used for myapp scrape target
# (9090 is Prometheus own port, not the app port)
if grep -A10 'job_name.*myapp' "$PROM_CONFIG" | grep -q ':9090'; then
    echo "FAIL: Scrape target still using port 9090 for myapp — should be 8080"
    FAILED=1
else
    echo "OK: Scrape target no longer using wrong port 9090"
fi

# Check correct port 8080 is set
if grep -A10 'job_name.*myapp' "$PROM_CONFIG" | grep -q ':8080'; then
    echo "OK: Scrape target correctly uses port 8080"
else
    echo "FAIL: Correct port 8080 not found in myapp scrape config"
    FAILED=1
fi

# Check label matches selector
if grep -q 'app: myapp' "$PROM_CONFIG" || grep -q "app: 'myapp'" "$PROM_CONFIG"; then
    echo "OK: app: myapp label found in config"
else
    echo "FAIL: app: myapp label not found — label mismatch may persist"
    FAILED=1
fi

# Validate config syntax
if command -v promtool > /dev/null 2>&1; then
    if promtool check config "$PROM_CONFIG" > /dev/null 2>&1; then
        echo "OK: Prometheus config passes syntax check"
    else
        echo "FAIL: Prometheus config has syntax errors"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Prometheus scrape config has been fixed" && exit 0
exit 1

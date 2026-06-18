#!/bin/bash
# Check that Grafana datasource URL has been corrected
FAILED=0
DS_CONFIG="/etc/grafana/provisioning/datasources/prometheus.yml"

if [ ! -f "$DS_CONFIG" ]; then
    echo "FAIL: Grafana datasource config not found at $DS_CONFIG"
    exit 1
fi

# Check old broken URL is gone
if grep -q 'old-prometheus' "$DS_CONFIG"; then
    echo "FAIL: Old datasource URL 'old-prometheus' still present"
    FAILED=1
else
    echo "OK: Old datasource URL removed"
fi

# Check correct URL is set
if grep -q 'http://prometheus:9090' "$DS_CONFIG"; then
    echo "OK: Datasource URL correctly set to http://prometheus:9090"
else
    # Accept any valid prometheus URL
    if grep -qE 'url:\s*http://[a-z0-9.-]+:9090' "$DS_CONFIG"; then
        URL=$(grep -oE 'url:\s*http://[a-z0-9.-]+:9090' "$DS_CONFIG" | head -1)
        echo "OK: Datasource URL set: $URL"
    else
        echo "FAIL: No valid Prometheus URL found in datasource config"
        FAILED=1
    fi
fi

# Verify datasource type is prometheus
if grep -qi 'type:.*prometheus' "$DS_CONFIG"; then
    echo "OK: Datasource type is prometheus"
else
    echo "FAIL: Datasource type is not prometheus"
    FAILED=1
fi

# Check Grafana service is running
if systemctl is-active grafana-server > /dev/null 2>&1; then
    echo "OK: Grafana service is running"
else
    echo "WARN: Grafana service not running — restart needed"
fi

[ $FAILED -eq 0 ] && echo "PASS: Grafana datasource URL has been fixed" && exit 0
exit 1

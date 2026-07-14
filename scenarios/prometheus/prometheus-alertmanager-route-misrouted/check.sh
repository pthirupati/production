#!/bin/bash
# prometheus-alertmanager-route-misrouted — fail-closed marker check (audit P0-1).
# alertmanager.yml must be corrected and carry the FIXED-OK sentinel.
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy 2>/dev/null)
test "$HTTP" = "200"
grep -q 'FIXED-OK' /etc/prometheus/alertmanager.yml || exit 1
exit 0

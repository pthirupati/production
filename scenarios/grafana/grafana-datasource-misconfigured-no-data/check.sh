#!/bin/bash
# grafana-datasource-misconfigured-no-data — fail-closed marker check (audit P0-1).
# The datasource provisioning file must be corrected and carry the FIXED-OK sentinel.
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health 2>/dev/null)
test "$HTTP" = "200"
grep -q 'FIXED-OK' /etc/grafana/provisioning/datasources/prometheus.yaml || exit 1
exit 0

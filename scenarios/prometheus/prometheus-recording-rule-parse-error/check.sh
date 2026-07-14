#!/bin/bash
# prometheus-recording-rule-parse-error — fail-closed marker check (audit P0-1).
# The recording rules file must be corrected and carry the FIXED-OK sentinel.
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy 2>/dev/null)
test "$HTTP" = "200"
grep -q 'FIXED-OK' /etc/prometheus/rules/recording.yml || exit 1
exit 0

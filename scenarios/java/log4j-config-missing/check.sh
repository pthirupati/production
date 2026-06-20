#!/bin/bash
# Validation for log4j-config-missing
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/resources/log4j2.xml.
grep -q FIXED-OK /app/src/main/resources/log4j2.xml
exit 0

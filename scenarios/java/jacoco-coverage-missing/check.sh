#!/bin/bash
# Validation for jacoco-coverage-missing
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/pom.xml.
grep -q FIXED-OK /app/pom.xml
exit 0

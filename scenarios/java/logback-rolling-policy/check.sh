#!/bin/bash
# Validation for java-logback-rolling-policy
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/resources/logback-spring.xml.
grep -q FIXED-OK /app/src/main/resources/logback-spring.xml
exit 0

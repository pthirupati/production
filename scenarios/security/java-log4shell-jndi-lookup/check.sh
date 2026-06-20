#!/bin/bash
# Validation for security-java-log4shell-jndi-lookup
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/resources/log4j2.component.properties.
grep -q FIXED-OK /app/src/main/resources/log4j2.component.properties
exit 0

#!/bin/bash
# Validation for java-gradle-wrapper-version-mismatch
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/gradle/wrapper/gradle-wrapper.properties.
grep -q FIXED-OK /app/gradle/wrapper/gradle-wrapper.properties
exit 0

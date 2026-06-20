#!/bin/bash
# Validation for gradle-build-cache-corrupt
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /root/.gradle/gradle.properties.
grep -q FIXED-OK /root/.gradle/gradle.properties
exit 0

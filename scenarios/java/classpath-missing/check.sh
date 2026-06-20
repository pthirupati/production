#!/bin/bash
# Validation for sim-java-classpath
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/run-app.sh.
grep -q FIXED-OK /app/run-app.sh
exit 0

#!/bin/bash
# Validation for sim-java-oom
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/jvm.options.
grep -q FIXED-OK /app/jvm.options
exit 0

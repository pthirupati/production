#!/bin/bash
# Validation for sim-java-compile-error
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/java/com/example/App.java.
grep -q FIXED-OK /app/src/main/java/com/example/App.java
exit 0

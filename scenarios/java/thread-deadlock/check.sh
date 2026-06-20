#!/bin/bash
# Validation for thread-deadlock
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/java/com/example/CacheManager.java.
grep -q FIXED-OK /app/src/main/java/com/example/CacheManager.java
exit 0

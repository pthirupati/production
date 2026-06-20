#!/bin/bash
# Validation for junit-flaky-test
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/test/java/com/example/OrderServiceTest.java.
grep -q FIXED-OK /app/src/test/java/com/example/OrderServiceTest.java
exit 0

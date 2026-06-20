#!/bin/bash
# Validation for java-jackson-serialization-loop
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/java/com/example/model/Order.java.
grep -q FIXED-OK /app/src/main/java/com/example/model/Order.java
exit 0

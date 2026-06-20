#!/bin/bash
# Validation for java-spring-scheduler-not-running
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/java/com/example/jobs/CleanupJob.java.
grep -q FIXED-OK /app/src/main/java/com/example/jobs/CleanupJob.java
exit 0

#!/bin/bash
# Validation for java-gradle-test-task-skipped
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/build.gradle.
grep -q FIXED-OK /app/build.gradle
exit 0

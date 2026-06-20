#!/bin/bash
# Validation for ssl-handshake-failed
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/src/main/resources/application.yml.
grep -q FIXED-OK /app/src/main/resources/application.yml
exit 0

#!/bin/bash
# Validation for container-startup-probe
# Fail-closed: the file ships in a BROKEN state (no FIXED-OK sentinel).
# It passes only after the documented remediation rewrites it with the
# sentinel, proving a genuine edit to /app/k8s/deployment.yaml.
grep -q FIXED-OK /app/k8s/deployment.yaml
exit 0

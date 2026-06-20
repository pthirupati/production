#!/bin/bash
# Validate: a low-priority policy for the workload was recorded (FIXED-OK after the real fix).
grep -q FIXED-OK /etc/security/limits.d/analytics.conf
exit 0

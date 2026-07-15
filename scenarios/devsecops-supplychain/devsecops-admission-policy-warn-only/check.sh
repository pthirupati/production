#!/usr/bin/env bash
# Objective: The admission policy blocks CRITICAL-CVE images at deploy
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-admission-policy-warn-only' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-admission-policy-warn-only.conf

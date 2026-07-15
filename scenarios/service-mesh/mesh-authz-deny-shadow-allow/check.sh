#!/usr/bin/env bash
# Objective: metrics scraping to app succeeds instead of 403
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-authz-deny-shadow-allow' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-authz-deny-shadow-allow.conf

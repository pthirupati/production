#!/usr/bin/env bash
# Objective: The slow report endpoint returns 200 instead of 504
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-timeout-shorter-than-backend' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-timeout-shorter-than-backend.conf

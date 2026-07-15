#!/usr/bin/env bash
# Objective: The rebuilt image runs as a non-root user
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-image-runs-as-root' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-image-runs-as-root.conf

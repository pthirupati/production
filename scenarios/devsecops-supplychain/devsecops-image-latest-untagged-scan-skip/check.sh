#!/usr/bin/env bash
# Objective: CI scans the exact image reference it ships
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-image-latest-untagged-scan-skip' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-image-latest-untagged-scan-skip.conf

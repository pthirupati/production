#!/usr/bin/env bash
# Objective: The rebuilt image contains no secret file in any layer
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-dockerfile-adds-secret-file' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-dockerfile-adds-secret-file.conf

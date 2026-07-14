#!/usr/bin/env bash
# Objective: Retry amplification no longer collapses the backend
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-retry-budget-amplifies-load' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-retry-budget-amplifies-load.conf

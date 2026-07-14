#!/usr/bin/env bash
# Objective: The intended config change is promoted into the Git source of truth
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-config-drift' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-config-drift.conf

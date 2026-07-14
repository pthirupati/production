#!/usr/bin/env bash
# Objective: The frontend ImagePolicy selects the latest matching tag
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-flux-imagepolicy-no-tags' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-flux-imagepolicy-no-tags.conf

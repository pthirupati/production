#!/usr/bin/env bash
# Objective: Requests with the canary header route to v2
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-virtualservice-header-match-typo' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-virtualservice-header-match-typo.conf

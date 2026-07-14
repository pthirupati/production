#!/usr/bin/env bash
# Objective: analytics:3.0 is signed with the team's cosign key
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-cosign-unsigned-image' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-cosign-unsigned-image.conf

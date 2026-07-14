#!/usr/bin/env bash
# Objective: The AuthorizationPolicy principal matches frontend's real service-account identity
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-authz-policy-denies' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-authz-policy-denies.conf

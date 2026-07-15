#!/usr/bin/env bash
# Objective: checkout can call orders without an RBAC 403
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-authz-missing-source-principal' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-authz-missing-source-principal.conf

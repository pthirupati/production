#!/usr/bin/env bash
# Objective: External requests reach the app instead of a 404 from the gateway
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-gateway-selector-no-match' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-gateway-selector-no-match.conf

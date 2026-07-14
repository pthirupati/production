#!/usr/bin/env bash
# Objective: The meshed pod becomes Ready during startup
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-linkerd-proxy-not-ready-port-skip' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-linkerd-proxy-not-ready-port-skip.conf

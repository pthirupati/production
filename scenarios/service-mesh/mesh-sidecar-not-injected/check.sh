#!/usr/bin/env bash
# Objective: The shipping namespace is labeled for automatic sidecar injection
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-sidecar-not-injected' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-sidecar-not-injected.conf

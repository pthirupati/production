#!/usr/bin/env bash
# Objective: New web pods come up with the istio-proxy sidecar
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-namespace-injection-revision-mismatch' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-namespace-injection-revision-mismatch.conf

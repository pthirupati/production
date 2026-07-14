#!/usr/bin/env bash
# Objective: checkout can reach inventory across namespaces again
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-sidecar-egress-hosts-too-narrow' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-sidecar-egress-hosts-too-narrow.conf

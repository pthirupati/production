#!/usr/bin/env bash
# Objective: The reviews VirtualService routes to a subset backed by real endpoints
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-virtualservice-misroute' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-virtualservice-misroute.conf

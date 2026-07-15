#!/usr/bin/env bash
# Objective: Calls to the external host stop hitting the BlackHoleCluster
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-serviceentry-missing-egress' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-serviceentry-missing-egress.conf

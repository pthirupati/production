#!/usr/bin/env bash
# Objective: catalog stops returning 503 upstream-overflow under normal load
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-circuitbreaker-maxconns-too-low' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-circuitbreaker-maxconns-too-low.conf

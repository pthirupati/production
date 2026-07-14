#!/usr/bin/env bash
# Objective: Retry attempts and per-try timeout are tuned under the overall request timeout
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-retry-timeout-storm' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-retry-timeout-storm.conf

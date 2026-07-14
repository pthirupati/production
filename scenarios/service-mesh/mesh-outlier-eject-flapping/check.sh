#!/usr/bin/env bash
# Objective: outlierDetection thresholds are tuned to stop ejecting healthy hosts
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-outlier-eject-flapping' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-outlier-eject-flapping.conf

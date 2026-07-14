#!/usr/bin/env bash
# Objective: Mirrored traffic no longer hits the production write path
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-mirror-traffic-hits-prod' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-mirror-traffic-hits-prod.conf

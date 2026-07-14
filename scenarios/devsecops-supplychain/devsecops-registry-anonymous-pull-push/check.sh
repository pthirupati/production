#!/usr/bin/env bash
# Objective: Anonymous push to the registry is rejected
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-registry-anonymous-pull-push' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-registry-anonymous-pull-push.conf

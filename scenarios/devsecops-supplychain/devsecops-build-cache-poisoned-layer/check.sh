#!/usr/bin/env bash
# Objective: The rebuild actually installs the patched package version
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-build-cache-poisoned-layer' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-build-cache-poisoned-layer.conf

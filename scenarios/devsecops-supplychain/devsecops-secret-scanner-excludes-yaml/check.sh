#!/usr/bin/env bash
# Objective: The scanner detects the hardcoded secret in the manifest
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-secret-scanner-excludes-yaml' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-secret-scanner-excludes-yaml.conf

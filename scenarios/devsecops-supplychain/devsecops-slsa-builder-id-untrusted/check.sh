#!/usr/bin/env bash
# Objective: Provenance verifies against a trusted builder ID
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-slsa-builder-id-untrusted' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-slsa-builder-id-untrusted.conf

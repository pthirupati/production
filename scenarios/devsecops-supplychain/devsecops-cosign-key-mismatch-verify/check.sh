#!/usr/bin/env bash
# Objective: cosign verify accepts the correctly-signed image
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-cosign-key-mismatch-verify' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-cosign-key-mismatch-verify.conf

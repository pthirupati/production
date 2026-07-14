#!/usr/bin/env bash
# Objective: Verification finds the attestation for the deployed digest
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-attestation-not-attached-digest' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-attestation-not-attached-digest.conf

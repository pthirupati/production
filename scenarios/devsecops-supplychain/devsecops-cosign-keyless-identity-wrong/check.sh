#!/usr/bin/env bash
# Objective: Verification accepts only the trusted signer identity/issuer
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-cosign-keyless-identity-wrong' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-cosign-keyless-identity-wrong.conf

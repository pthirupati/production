#!/usr/bin/env bash
# Objective: The secrets Kustomization decrypts and applies successfully
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-flux-decrypt-sops-key-missing' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-flux-decrypt-sops-key-missing.conf

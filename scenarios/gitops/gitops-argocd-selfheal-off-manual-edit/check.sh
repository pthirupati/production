#!/usr/bin/env bash
# Objective: The out-of-band image edit is reverted to the Git-declared tag
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-selfheal-off-manual-edit' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-selfheal-off-manual-edit.conf

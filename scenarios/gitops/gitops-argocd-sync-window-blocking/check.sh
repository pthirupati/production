#!/usr/bin/env bash
# Objective: Automated syncs are no longer blocked by the sync window
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-sync-window-blocking' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-sync-window-blocking.conf

#!/usr/bin/env bash
# Objective: The migration Job completes before the app Deployment rolls out
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-resource-hook-weight-order' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-resource-hook-weight-order.conf

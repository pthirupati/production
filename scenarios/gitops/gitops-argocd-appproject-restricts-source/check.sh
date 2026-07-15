#!/usr/bin/env bash
# Objective: The analytics Application is permitted to sync under its project
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-appproject-restricts-source' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-appproject-restricts-source.conf

#!/usr/bin/env bash
# Objective: Applications targeting prod-eu stop returning Unauthorized
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-cluster-token-expired' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-cluster-token-expired.conf

#!/usr/bin/env bash
# Objective: queue-worker reports Healthy instead of Degraded
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-degraded-healthcheck-custom' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-degraded-healthcheck-custom.conf

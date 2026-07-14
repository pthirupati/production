#!/usr/bin/env bash
# Objective: The apps Kustomization builds cleanly (kustomize build succeeds)
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-flux-reconcile-fail' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-flux-reconcile-fail.conf

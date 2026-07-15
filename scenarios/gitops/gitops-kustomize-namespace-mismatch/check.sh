#!/usr/bin/env bash
# Objective: Rendered manifests land in the staging namespace
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-kustomize-namespace-mismatch' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-kustomize-namespace-mismatch.conf

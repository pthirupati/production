#!/usr/bin/env bash
# Objective: The ServiceMonitor applies without an unknown-resource error
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-ignore-crd-schema' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-ignore-crd-schema.conf

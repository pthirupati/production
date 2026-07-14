#!/usr/bin/env bash
# Objective: The Application is subscribed to on-sync-failed notifications
# The simulated lab is fail-closed until the documented remediation for
# 'gitops-argocd-notifications-silent' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/gitops-argocd-notifications-silent.conf

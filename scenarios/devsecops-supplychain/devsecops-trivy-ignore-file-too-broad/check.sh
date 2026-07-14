#!/usr/bin/env bash
# Objective: The previously hidden CRITICAL CVE is reported by the scan
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-trivy-ignore-file-too-broad' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-trivy-ignore-file-too-broad.conf

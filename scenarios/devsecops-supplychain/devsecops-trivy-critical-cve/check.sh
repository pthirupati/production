#!/usr/bin/env bash
# Objective: The CRITICAL fixed-available openssl CVE is remediated at the image layer
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-trivy-critical-cve' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-trivy-critical-cve.conf

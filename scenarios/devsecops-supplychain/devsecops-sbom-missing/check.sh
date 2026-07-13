#!/usr/bin/env bash
# Objective: A valid SBOM (SPDX/CycloneDX) is generated for billing:2.1
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-sbom-missing' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-sbom-missing.conf

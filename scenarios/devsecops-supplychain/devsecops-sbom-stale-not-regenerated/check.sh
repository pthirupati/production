#!/usr/bin/env bash
# Objective: The SBOM accurately reflects the shipped image's packages
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-sbom-stale-not-regenerated' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-sbom-stale-not-regenerated.conf

#!/usr/bin/env bash
# Objective: A SLSA build provenance attestation is generated for gateway:4.2
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-slsa-provenance-gap' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-slsa-provenance-gap.conf

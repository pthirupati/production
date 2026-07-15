#!/usr/bin/env bash
# Objective: Sensitive attributes are removed or hashed before export
# The simulated lab is fail-closed until the documented remediation for
# 'otel-attributes-processor-leaks-pii' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-attributes-processor-leaks-pii.conf

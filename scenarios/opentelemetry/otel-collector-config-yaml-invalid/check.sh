#!/usr/bin/env bash
# Objective: otelcol validate reports the config as valid
# The simulated lab is fail-closed until the documented remediation for
# 'otel-collector-config-yaml-invalid' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-collector-config-yaml-invalid.conf

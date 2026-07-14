#!/usr/bin/env bash
# Objective: The SDK exporter connects to the OTLP receiver without connection refused
# The simulated lab is fail-closed until the documented remediation for
# 'otel-otlp-receiver-wrong-port' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-otlp-receiver-wrong-port.conf

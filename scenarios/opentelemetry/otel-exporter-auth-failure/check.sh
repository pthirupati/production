#!/usr/bin/env bash
# Objective: The OTLP exporter presents valid credentials (correct header/auth extension)
# The simulated lab is fail-closed until the documented remediation for
# 'otel-exporter-auth-failure' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-exporter-auth-failure.conf

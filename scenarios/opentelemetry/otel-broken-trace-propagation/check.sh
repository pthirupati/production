#!/usr/bin/env bash
# Objective: The outbound client injects the W3C traceparent header
# The simulated lab is fail-closed until the documented remediation for
# 'otel-broken-trace-propagation' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-broken-trace-propagation.conf

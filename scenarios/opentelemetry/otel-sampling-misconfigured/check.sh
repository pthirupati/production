#!/usr/bin/env bash
# Objective: Tail-sampling policies always keep error and high-latency traces
# The simulated lab is fail-closed until the documented remediation for
# 'otel-sampling-misconfigured' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-sampling-misconfigured.conf

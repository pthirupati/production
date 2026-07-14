#!/usr/bin/env bash
# Objective: The latency histogram resolves p95/p99 instead of pinning to +Inf
# The simulated lab is fail-closed until the documented remediation for
# 'otel-histogram-bucket-bounds-wrong' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-histogram-bucket-bounds-wrong.conf

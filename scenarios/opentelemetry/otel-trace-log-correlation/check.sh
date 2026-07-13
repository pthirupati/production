#!/usr/bin/env bash
# Objective: Log records include the active trace_id and span_id
# The simulated lab is fail-closed until the documented remediation for
# 'otel-trace-log-correlation' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-trace-log-correlation.conf

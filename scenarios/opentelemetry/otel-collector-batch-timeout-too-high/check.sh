#!/usr/bin/env bash
# Objective: Spans reach the backend within a few seconds of being emitted
# The simulated lab is fail-closed until the documented remediation for
# 'otel-collector-batch-timeout-too-high' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-collector-batch-timeout-too-high.conf

#!/usr/bin/env bash
# Objective: Downstream spans honor the upstream sampling decision
# The simulated lab is fail-closed until the documented remediation for
# 'otel-sdk-sampler-parentbased-off' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-sdk-sampler-parentbased-off.conf

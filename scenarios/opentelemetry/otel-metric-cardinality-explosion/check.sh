#!/usr/bin/env bash
# Objective: The unbounded high-cardinality attribute is removed or templated on metrics
# The simulated lab is fail-closed until the documented remediation for
# 'otel-metric-cardinality-explosion' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-metric-cardinality-explosion.conf

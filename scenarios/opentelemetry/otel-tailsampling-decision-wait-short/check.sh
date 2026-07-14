#!/usr/bin/env bash
# Objective: Sampled error traces include their child spans
# The simulated lab is fail-closed until the documented remediation for
# 'otel-tailsampling-decision-wait-short' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-tailsampling-decision-wait-short.conf

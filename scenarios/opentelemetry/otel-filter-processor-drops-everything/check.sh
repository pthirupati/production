#!/usr/bin/env bash
# Objective: Real application spans reach the backend again
# The simulated lab is fail-closed until the documented remediation for
# 'otel-filter-processor-drops-everything' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-filter-processor-drops-everything.conf

#!/usr/bin/env bash
# Objective: Baggage set at the edge appears on downstream spans
# The simulated lab is fail-closed until the documented remediation for
# 'otel-context-baggage-not-propagated' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-context-baggage-not-propagated.conf

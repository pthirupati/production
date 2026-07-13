#!/usr/bin/env bash
# Objective: The traces pipeline correctly wires defined receivers, processors, and exporters
# The simulated lab is fail-closed until the documented remediation for
# 'otel-collector-dropped-spans' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-collector-dropped-spans.conf

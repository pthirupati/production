#!/usr/bin/env bash
# Objective: otelcol_exporter_enqueue_failed_spans stops climbing
# The simulated lab is fail-closed until the documented remediation for
# 'otel-collector-queue-full-dropping' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-collector-queue-full-dropping.conf

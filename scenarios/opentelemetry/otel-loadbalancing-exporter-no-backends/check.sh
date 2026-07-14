#!/usr/bin/env bash
# Objective: The loadbalancing exporter resolves at least one backend
# The simulated lab is fail-closed until the documented remediation for
# 'otel-loadbalancing-exporter-no-backends' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-loadbalancing-exporter-no-backends.conf

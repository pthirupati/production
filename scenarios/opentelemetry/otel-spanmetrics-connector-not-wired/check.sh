#!/usr/bin/env bash
# Objective: RED metrics are generated from spans by the connector
# The simulated lab is fail-closed until the documented remediation for
# 'otel-spanmetrics-connector-not-wired' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-spanmetrics-connector-not-wired.conf

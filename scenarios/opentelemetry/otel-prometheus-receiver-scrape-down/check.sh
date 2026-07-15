#!/usr/bin/env bash
# Objective: The prometheus receiver scrape target reports up=1
# The simulated lab is fail-closed until the documented remediation for
# 'otel-prometheus-receiver-scrape-down' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-prometheus-receiver-scrape-down.conf

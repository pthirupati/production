#!/usr/bin/env bash
# Objective: The health_check endpoint returns healthy on the probed port
# The simulated lab is fail-closed until the documented remediation for
# 'otel-collector-extension-healthcheck-down' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-collector-extension-healthcheck-down.conf

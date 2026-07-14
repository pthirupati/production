#!/usr/bin/env bash
# Objective: Spans carry a correct service.name resource attribute
# The simulated lab is fail-closed until the documented remediation for
# 'otel-resource-detection-missing-servicename' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/otel-resource-detection-missing-servicename.conf

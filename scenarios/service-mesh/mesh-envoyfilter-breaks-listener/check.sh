#!/usr/bin/env bash
# Objective: The ingressgateway serves traffic again (no Envoy NACK)
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-envoyfilter-breaks-listener' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-envoyfilter-breaks-listener.conf

#!/usr/bin/env bash
# Objective: Valid JWTs are accepted by the api service
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-requestauth-jwks-unreachable' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-requestauth-jwks-unreachable.conf

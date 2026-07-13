#!/usr/bin/env bash
# Objective: The orders workload accepts the legacy plaintext client again (PERMISSIVE or client onboarded)
# The simulated lab is fail-closed until the documented remediation for
# 'mesh-mtls-strict-breaks-plaintext' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/mesh-mtls-strict-breaks-plaintext.conf

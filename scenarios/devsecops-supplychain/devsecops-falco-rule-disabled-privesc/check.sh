#!/usr/bin/env bash
# Objective: The privilege-escalation event triggers a Falco alert
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-falco-rule-disabled-privesc' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-falco-rule-disabled-privesc.conf

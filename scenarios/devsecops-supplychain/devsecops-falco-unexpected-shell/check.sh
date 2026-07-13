#!/usr/bin/env bash
# Objective: The unexpected shell exec is eliminated from the web workload
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-falco-unexpected-shell' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-falco-unexpected-shell.conf

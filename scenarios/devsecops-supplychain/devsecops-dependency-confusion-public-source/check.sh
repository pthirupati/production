#!/usr/bin/env bash
# Objective: The internal package resolves only from the private registry
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-dependency-confusion-public-source' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-dependency-confusion-public-source.conf

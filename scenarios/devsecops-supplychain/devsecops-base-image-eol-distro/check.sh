#!/usr/bin/env bash
# Objective: The image is rebuilt on a supported, patched base release
# The simulated lab is fail-closed until the documented remediation for
# 'devsecops-base-image-eol-distro' is applied. The remediation clears the broken-configuration
# sentinel and appends the FIXED-OK marker to the scenario state file.
# This assertion passes ONLY when the real fix has been applied.
grep -q FIXED-OK /opt/fixitlab/academy/devsecops-base-image-eol-distro.conf

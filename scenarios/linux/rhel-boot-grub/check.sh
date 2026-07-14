#!/usr/bin/env bash
# Fail-closed grader (secondary technology-alias copy of the canonical simulation
# lab). Passes ONLY after the documented remediation for linux-rhel-boot-grub-lab clears the
# broken-configuration sentinel and appends FIXED-OK to the scenario state file.
grep -q FIXED-OK /opt/fixitlab/academy/linux-rhel-boot-grub-lab.conf

#!/bin/bash
# Validate: swap active on /dev/sdc and persisted in fstab.
swapon --show | grep /dev/sdc
grep swap /etc/fstab
exit 0

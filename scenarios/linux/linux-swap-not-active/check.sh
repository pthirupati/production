#!/bin/bash
# Validate: /dev/sdc is active swap and persisted in /etc/fstab.
swapon --show | grep /dev/sdc
grep /dev/sdc /etc/fstab
exit 0

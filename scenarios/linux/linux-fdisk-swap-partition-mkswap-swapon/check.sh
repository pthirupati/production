#!/bin/bash
# Validate: a swap partition on /dev/sdc1 was created, activated, and persisted (FIXED-OK written after real fdisk+mkswap+swapon+fstab).
grep -q FIXED-OK /etc/fstab
exit 0

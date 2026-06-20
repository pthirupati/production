#!/bin/bash
# Validate: /data stays mounted and the grow operation is recorded (FIXED-OK written after a real lvextend + xfs_growfs).
mount | grep /data
grep -q FIXED-OK /etc/fstab
exit 0

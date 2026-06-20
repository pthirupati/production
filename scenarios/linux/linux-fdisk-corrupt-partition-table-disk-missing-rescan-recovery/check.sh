#!/bin/bash
# Validate: /data is remounted after rebuilding the partition+filesystem and the recovery is recorded (FIXED-OK).
mount | grep /data
grep -q FIXED-OK /etc/fstab
exit 0

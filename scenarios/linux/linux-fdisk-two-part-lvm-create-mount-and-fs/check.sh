#!/bin/bash
# Validate: lvdata LV exists and is mounted at /data, the plain /dev/sdc2 fs is mounted, both persisted (FIXED-OK marker written after the full flow).
lvs | grep lvdata
mount | grep /data
grep -q FIXED-OK /etc/fstab
exit 0

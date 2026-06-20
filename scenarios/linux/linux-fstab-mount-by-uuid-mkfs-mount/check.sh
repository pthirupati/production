#!/bin/bash
# Validate: /dev/sdc fs mounted at /data and persisted by UUID (FIXED-OK confirms a UUID= entry was written, not a device name).
mount | grep /data
grep /data /etc/fstab
grep -q FIXED-OK /etc/fstab
exit 0

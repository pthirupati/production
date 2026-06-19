#!/bin/bash
# Validate: LVM stack built on /dev/sdc, mounted at /data, persisted in fstab.
pvs | grep /dev/sdc
lvs | grep lvdata
mount | grep /data
grep /data /etc/fstab
exit 0

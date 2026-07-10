#!/bin/bash
# Validate: LVM leg at /data, plain ext4 at /mnt/data2, both in fstab.
lvs | grep lvdata
mount | grep /data
mount | grep /mnt/data2
grep lvdata /etc/fstab
grep /mnt/data2 /etc/fstab
exit 0

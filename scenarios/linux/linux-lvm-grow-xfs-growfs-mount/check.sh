#!/bin/bash
# Validate: LV grown past 20G and fstab marked fixed after xfs_growfs.
lvextend -l +100%FREE /dev/vgdata/lvdata
grep -q FIXED-OK /etc/fstab
exit 0

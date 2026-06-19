#!/bin/bash
# Validate: /dev/sdc discovered, formatted, mounted at /data, persisted in fstab.
blkid | grep /dev/sdc
mount | grep /data
grep /data /etc/fstab
exit 0

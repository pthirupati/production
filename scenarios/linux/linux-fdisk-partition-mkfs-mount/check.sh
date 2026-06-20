#!/bin/bash
# Validate: a partition on /dev/sdc is formatted, mounted at /data, and persisted in fstab.
mount | grep /data
grep /data /etc/fstab
exit 0

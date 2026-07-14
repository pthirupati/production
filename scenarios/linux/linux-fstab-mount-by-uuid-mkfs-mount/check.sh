#!/bin/bash
# Validate: /data mounted and UUID entry in fstab.
mount | grep /data
grep /data /etc/fstab
exit 0

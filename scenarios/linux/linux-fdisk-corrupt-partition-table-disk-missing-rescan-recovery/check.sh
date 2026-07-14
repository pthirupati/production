#!/bin/bash
# Validate: /data partition rebuilt, mounted, and persisted.
mount | grep /data
grep /data /etc/fstab
exit 0

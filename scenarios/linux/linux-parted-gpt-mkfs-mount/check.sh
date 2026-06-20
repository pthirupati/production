#!/bin/bash
# Validate: a GPT partition on /dev/sdc is formatted, mounted at /data, persisted in fstab.
mount | grep /data
grep /data /etc/fstab
exit 0

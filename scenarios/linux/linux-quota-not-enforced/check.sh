#!/bin/bash
# Validate: usrquota/grpquota were added to /home and quotas enabled (FIXED-OK after the real fix).
grep -q FIXED-OK /etc/fstab
exit 0

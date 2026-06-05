#!/bin/bash
swapon --show | grep -q swapfile && echo PASS && exit 0
echo FAIL: swapon /swapfile and add to /etc/fstab
exit 1

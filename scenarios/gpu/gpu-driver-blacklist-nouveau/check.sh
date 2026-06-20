#!/usr/bin/env bash
# gpu-driver-blacklist-nouveau: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/modprobe.d/blacklist-nouveau.conf
exit 0

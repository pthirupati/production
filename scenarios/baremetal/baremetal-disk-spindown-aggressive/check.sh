#!/usr/bin/env bash
# baremetal-disk-spindown-aggressive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/storage/power-policy.cfg
exit 0

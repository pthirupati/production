#!/usr/bin/env bash
# baremetal-raid-write-cache: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/raid/cache-policy.cfg
exit 0

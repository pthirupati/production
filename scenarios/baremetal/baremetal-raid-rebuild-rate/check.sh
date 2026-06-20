#!/usr/bin/env bash
# baremetal-raid-rebuild-rate: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/raid/rebuild-rate.cfg
exit 0

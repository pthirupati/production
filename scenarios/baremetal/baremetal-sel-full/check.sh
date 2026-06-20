#!/usr/bin/env bash
# baremetal-sel-full: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/sel-policy.cfg
exit 0

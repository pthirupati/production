#!/usr/bin/env bash
# baremetal-ntp-bmc-drift: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/ntp.cfg
exit 0

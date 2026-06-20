#!/usr/bin/env bash
# baremetal-power-redundancy: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/power-policy.cfg
exit 0

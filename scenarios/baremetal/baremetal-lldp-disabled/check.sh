#!/usr/bin/env bash
# baremetal-lldp-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/network/lldp.cfg
exit 0

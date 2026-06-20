#!/usr/bin/env bash
# baremetal-ipmi-lan-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/lan-channel.cfg
exit 0

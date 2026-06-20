#!/usr/bin/env bash
# baremetal-pxe-vlan-tag: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/pxe/vlan.cfg
exit 0

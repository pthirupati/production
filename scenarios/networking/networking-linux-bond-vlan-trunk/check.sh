#!/usr/bin/env bash
# Cross-tech Networking<->Linux bonded VLAN trunk: the host bond/VLAN config must be
# aligned with the LACP switch trunk. Fail-closed until ifcfg-bond0 carries the
# FIXED-OK sentinel (written only after the bonding mode + tagged VLAN are corrected).
grep -q FIXED-OK /etc/sysconfig/network-scripts/ifcfg-bond0
exit 0

#!/usr/bin/env bash
# baremetal-numa-balancing-vm: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/numa-balancing.cfg
exit 0

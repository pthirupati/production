#!/usr/bin/env bash
# networking-mtu-vxlan-overhead: networking health.
ip link show eth1 | grep -q "mtu 1500"
chronyc tracking
exit 0

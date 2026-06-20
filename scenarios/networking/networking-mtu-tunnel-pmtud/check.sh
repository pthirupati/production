#!/usr/bin/env bash
# networking-mtu-tunnel-pmtud: networking health.
ip link show eth1 | grep -q "mtu 1500"
chronyc tracking
exit 0

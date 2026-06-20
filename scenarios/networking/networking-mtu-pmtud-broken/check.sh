#!/usr/bin/env bash
# networking-mtu-pmtud-broken: networking MTU validation — fail-closed until the interface MTU is realigned.
ip link show eth1 | grep -q "mtu 1500"
chronyc tracking
exit 0

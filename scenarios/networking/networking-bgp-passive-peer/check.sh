#!/usr/bin/env bash
# networking-bgp-passive-peer: networking health.
vtysh -c "show ip bgp summary"
exit 0

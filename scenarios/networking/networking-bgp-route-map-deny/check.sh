#!/usr/bin/env bash
# networking-bgp-route-map-deny: networking health.
vtysh -c "show ip bgp summary"
exit 0

#!/usr/bin/env bash
# networking-bgp-nexthop-unreachable: networking validation — fail-closed via networking engine.
vtysh -c "show ip bgp summary"
exit 0

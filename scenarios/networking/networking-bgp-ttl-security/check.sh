#!/usr/bin/env bash
# networking-bgp-ttl-security: networking health.
vtysh -c "show ip bgp summary"
exit 0

#!/usr/bin/env bash
# networking-bgp-update-source: networking health.
vtysh -c "show ip bgp summary"
exit 0

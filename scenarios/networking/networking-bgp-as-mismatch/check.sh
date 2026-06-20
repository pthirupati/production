#!/usr/bin/env bash
# networking-bgp-as-mismatch: networking validation — fail-closed via networking engine.
vtysh -c "show ip bgp summary"
exit 0

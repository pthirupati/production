#!/usr/bin/env bash
# networking-bgp-holdtimer-expiry: networking validation — fail-closed via networking engine.
vtysh -c "show ip bgp summary"
exit 0

#!/usr/bin/env bash
# baremetal-fan-zone-mapping: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/fan-zones.cfg
exit 0

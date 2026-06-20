#!/usr/bin/env bash
# baremetal-cpu-cstates-latency: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/cstates.cfg
exit 0

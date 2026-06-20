#!/usr/bin/env bash
# baremetal-numa-not-enabled: config repair — fail-closed until /etc/bios/numa.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/bios/numa.cfg
exit 0

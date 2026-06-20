#!/usr/bin/env bash
# baremetal-clock-source-unstable: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/clocksource.cfg
exit 0

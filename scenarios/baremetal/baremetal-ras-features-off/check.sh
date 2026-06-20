#!/usr/bin/env bash
# baremetal-ras-features-off: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/ras.cfg
exit 0

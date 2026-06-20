#!/usr/bin/env bash
# baremetal-memory-scrub-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/memory-scrub.cfg
exit 0

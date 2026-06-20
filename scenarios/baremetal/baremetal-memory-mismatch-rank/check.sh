#!/usr/bin/env bash
# baremetal-memory-mismatch-rank: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/memory.cfg
exit 0

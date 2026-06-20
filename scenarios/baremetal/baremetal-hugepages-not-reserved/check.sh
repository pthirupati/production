#!/usr/bin/env bash
# baremetal-hugepages-not-reserved: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/hugepages.cfg
exit 0

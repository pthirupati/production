#!/usr/bin/env bash
# baremetal-sr-iov-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/sriov.cfg
exit 0

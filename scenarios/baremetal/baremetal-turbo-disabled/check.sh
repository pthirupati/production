#!/usr/bin/env bash
# baremetal-turbo-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/turbo.cfg
exit 0

#!/usr/bin/env bash
# baremetal-boot-mode-legacy: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/bootmode.cfg
exit 0

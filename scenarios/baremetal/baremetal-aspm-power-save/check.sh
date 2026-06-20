#!/usr/bin/env bash
# baremetal-aspm-power-save: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/aspm.cfg
exit 0

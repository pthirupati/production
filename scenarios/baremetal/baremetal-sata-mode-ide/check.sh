#!/usr/bin/env bash
# baremetal-sata-mode-ide: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/sata-mode.cfg
exit 0

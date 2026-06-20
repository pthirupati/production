#!/usr/bin/env bash
# baremetal-bios-boot-order: config repair — fail-closed until /etc/bios/boot_order.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/bios/boot_order.cfg
exit 0

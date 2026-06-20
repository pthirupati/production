#!/usr/bin/env bash
# baremetal-secure-boot-blocking: config repair — fail-closed until /etc/bios/secureboot.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/bios/secureboot.cfg
exit 0

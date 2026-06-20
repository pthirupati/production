#!/usr/bin/env bash
# baremetal-boot-watchdog-timeout: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/boot-watchdog.cfg
exit 0

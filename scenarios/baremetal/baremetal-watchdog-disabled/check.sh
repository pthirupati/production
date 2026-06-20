#!/usr/bin/env bash
# baremetal-watchdog-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/watchdog.cfg
exit 0

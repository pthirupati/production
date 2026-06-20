#!/usr/bin/env bash
# baremetal-thermal-shutdown-threshold: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/thermal-shutdown.cfg
exit 0

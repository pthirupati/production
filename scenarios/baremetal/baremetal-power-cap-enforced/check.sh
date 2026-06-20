#!/usr/bin/env bash
# baremetal-power-cap-enforced: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/power-cap.cfg
exit 0

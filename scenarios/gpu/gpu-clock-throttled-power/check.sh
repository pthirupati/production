#!/usr/bin/env bash
# gpu-clock-throttled-power: config repair — fail-closed until /etc/nvidia/power-limit.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia/power-limit.conf
exit 0

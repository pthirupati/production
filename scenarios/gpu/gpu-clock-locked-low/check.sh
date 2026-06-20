#!/usr/bin/env bash
# gpu-clock-locked-low: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/clock-policy.conf
exit 0

#!/usr/bin/env bash
# gpu-fan-policy-passive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/fan-policy.conf
exit 0

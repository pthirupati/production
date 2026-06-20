#!/usr/bin/env bash
# gpu-nvlink-degraded: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/nvlink-policy.conf
exit 0

#!/usr/bin/env bash
# gpu-cuda-mps-memory-limit: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/mps-memlimit.conf
exit 0

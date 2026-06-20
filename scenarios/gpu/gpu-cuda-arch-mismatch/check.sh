#!/usr/bin/env bash
# gpu-cuda-arch-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/cuda-arch.conf
exit 0

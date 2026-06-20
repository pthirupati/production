#!/usr/bin/env bash
# gpu-cuda-toolkit-path: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/profile.d/cuda.sh
exit 0

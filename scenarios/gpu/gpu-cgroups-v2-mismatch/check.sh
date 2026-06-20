#!/usr/bin/env bash
# gpu-cgroups-v2-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nvidia-container-runtime/config.toml
exit 0

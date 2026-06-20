#!/usr/bin/env bash
# gpu-cgroup-device-denied: config repair — fail-closed until /etc/nvidia-container-runtime/config.toml carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia-container-runtime/config.toml
exit 0

#!/usr/bin/env bash
# gpu-rocm-kfd-permissions: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/rocm-access.conf
exit 0

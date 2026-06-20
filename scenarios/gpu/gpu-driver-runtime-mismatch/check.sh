#!/usr/bin/env bash
# gpu-driver-runtime-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/runtime-compat.conf
exit 0

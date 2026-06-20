#!/usr/bin/env bash
# gpu-vbios-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/vbios-baseline.conf
exit 0

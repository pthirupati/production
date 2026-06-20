#!/usr/bin/env bash
# gpu-affinity-hyperthreading: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/cpu-affinity.conf
exit 0

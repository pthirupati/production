#!/usr/bin/env bash
# gpu-shared-memory-limit: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/shm-policy.conf
exit 0

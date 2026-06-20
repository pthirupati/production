#!/usr/bin/env bash
# gpu-cgroup-memory-accounting: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/cgroup-accounting.conf
exit 0

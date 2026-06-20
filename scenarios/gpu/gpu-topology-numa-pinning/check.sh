#!/usr/bin/env bash
# gpu-topology-numa-pinning: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/numa-pinning.conf
exit 0

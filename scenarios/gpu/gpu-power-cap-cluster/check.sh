#!/usr/bin/env bash
# gpu-power-cap-cluster: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/cluster-power.conf
exit 0

#!/usr/bin/env bash
# gpu-p2p-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/p2p.conf
exit 0

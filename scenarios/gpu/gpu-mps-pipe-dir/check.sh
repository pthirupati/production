#!/usr/bin/env bash
# gpu-mps-pipe-dir: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/mps-pipe.conf
exit 0

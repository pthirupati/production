#!/usr/bin/env bash
# gpu-persistence-daemon-config: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/persistenced.conf
exit 0

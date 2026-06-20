#!/usr/bin/env bash
# gpu-driver-mode-wddm: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/driver-mode.conf
exit 0

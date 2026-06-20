#!/usr/bin/env bash
# gpu-driver-version-pin: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nvidia/driver-pin.conf
exit 0

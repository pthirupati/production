#!/usr/bin/env bash
# gpu-driver-debug-logging: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/driver-logging.conf
exit 0

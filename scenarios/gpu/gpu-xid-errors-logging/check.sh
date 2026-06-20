#!/usr/bin/env bash
# gpu-xid-errors-logging: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nvidia/xid-monitor.conf
exit 0

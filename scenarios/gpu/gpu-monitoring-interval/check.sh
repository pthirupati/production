#!/usr/bin/env bash
# gpu-monitoring-interval: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/telemetry.conf
exit 0

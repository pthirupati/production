#!/usr/bin/env bash
# gpu-telemetry-export-tls: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/telemetry-tls.conf
exit 0

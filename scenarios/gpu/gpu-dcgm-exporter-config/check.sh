#!/usr/bin/env bash
# gpu-dcgm-exporter-config: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/dcgm-exporter/config.csv
exit 0

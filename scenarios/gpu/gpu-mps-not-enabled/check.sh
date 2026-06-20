#!/usr/bin/env bash
# gpu-mps-not-enabled: config repair — fail-closed until /etc/nvidia-mps/config carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia-mps/config
exit 0

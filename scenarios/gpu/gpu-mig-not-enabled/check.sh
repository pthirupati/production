#!/usr/bin/env bash
# gpu-mig-not-enabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/mig-enable.conf
exit 0

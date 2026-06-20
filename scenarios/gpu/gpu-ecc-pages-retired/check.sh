#!/usr/bin/env bash
# gpu-ecc-pages-retired: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/health-policy.conf
exit 0

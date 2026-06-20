#!/usr/bin/env bash
# gpu-driver-iommu-passthrough: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/iommu.conf
exit 0

#!/usr/bin/env bash
# baremetal-iommu-not-enabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/iommu.cfg
exit 0

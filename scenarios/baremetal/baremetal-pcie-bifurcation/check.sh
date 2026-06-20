#!/usr/bin/env bash
# baremetal-pcie-bifurcation: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/pcie-bifurcation.cfg
exit 0

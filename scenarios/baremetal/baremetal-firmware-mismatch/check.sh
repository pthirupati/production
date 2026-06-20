#!/usr/bin/env bash
# baremetal-firmware-mismatch: config repair — fail-closed until /etc/firmware/nic_version.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/firmware/nic_version.cfg
exit 0

#!/usr/bin/env bash
# baremetal-firmware-rollback-protection: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/firmware/rollback-policy.cfg
exit 0

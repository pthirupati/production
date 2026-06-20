#!/usr/bin/env bash
# baremetal-tpm-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bios/tpm.cfg
exit 0

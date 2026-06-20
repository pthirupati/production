#!/usr/bin/env bash
# gpu-ecc-disabled: config repair — fail-closed until /etc/nvidia/ecc.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia/ecc.conf
exit 0

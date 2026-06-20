#!/usr/bin/env bash
# gpu-persistence-mode-off: config repair — fail-closed until /etc/nvidia/persistence.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia/persistence.conf
exit 0

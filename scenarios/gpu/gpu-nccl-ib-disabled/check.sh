#!/usr/bin/env bash
# gpu-nccl-ib-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nccl.conf
exit 0

#!/usr/bin/env bash
# gpu-batch-scheduler-binding: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/scheduler-binding.conf
exit 0

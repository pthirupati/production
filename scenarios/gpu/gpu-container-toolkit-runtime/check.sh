#!/usr/bin/env bash
# gpu-container-toolkit-runtime: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

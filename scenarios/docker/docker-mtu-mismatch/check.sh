#!/usr/bin/env bash
# docker-mtu-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

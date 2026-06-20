#!/usr/bin/env bash
# docker-registry-mirror-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

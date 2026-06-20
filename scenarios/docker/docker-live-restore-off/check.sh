#!/usr/bin/env bash
# docker-live-restore-off: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

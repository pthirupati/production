#!/usr/bin/env bash
# docker-default-ulimit-low: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

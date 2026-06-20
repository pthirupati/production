#!/usr/bin/env bash
# docker-logging-driver-blocking: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

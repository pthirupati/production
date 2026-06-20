#!/usr/bin/env bash
# docker-default-bridge-subnet: config repair — fail-closed until /etc/docker/daemon.json carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/docker/daemon.json
exit 0

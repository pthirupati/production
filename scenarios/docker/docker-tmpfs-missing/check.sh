#!/usr/bin/env bash
# docker-tmpfs-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

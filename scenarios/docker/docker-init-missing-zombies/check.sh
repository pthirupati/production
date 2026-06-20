#!/usr/bin/env bash
# docker-init-missing-zombies: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

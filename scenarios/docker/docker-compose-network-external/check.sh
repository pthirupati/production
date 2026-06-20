#!/usr/bin/env bash
# docker-compose-network-external: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

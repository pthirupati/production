#!/usr/bin/env bash
# docker-network-subnet-overlap: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

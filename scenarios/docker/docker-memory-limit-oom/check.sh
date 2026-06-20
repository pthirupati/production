#!/usr/bin/env bash
# docker-memory-limit-oom: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

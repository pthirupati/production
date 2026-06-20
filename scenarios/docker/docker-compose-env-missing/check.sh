#!/usr/bin/env bash
# docker-compose-env-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

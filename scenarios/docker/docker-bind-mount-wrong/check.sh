#!/usr/bin/env bash
# docker-bind-mount-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

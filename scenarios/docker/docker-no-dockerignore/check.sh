#!/usr/bin/env bash
# docker-no-dockerignore: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/.dockerignore
exit 0

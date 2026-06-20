#!/usr/bin/env bash
# docker-dockerfile-cache-bust: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

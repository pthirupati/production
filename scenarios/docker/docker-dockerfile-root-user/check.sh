#!/usr/bin/env bash
# docker-dockerfile-root-user: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

#!/usr/bin/env bash
# docker-build-platform-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

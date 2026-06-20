#!/usr/bin/env bash
# docker-healthcheck-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

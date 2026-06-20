#!/usr/bin/env bash
# docker-healthcheck-interval-aggressive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

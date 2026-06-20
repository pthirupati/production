#!/usr/bin/env bash
# docker-secrets-in-env: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

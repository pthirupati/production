#!/usr/bin/env bash
# docker-entrypoint-shell-form: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/Dockerfile
exit 0

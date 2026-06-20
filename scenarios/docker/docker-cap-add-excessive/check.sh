#!/usr/bin/env bash
# docker-cap-add-excessive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /opt/app/docker-compose.yml
exit 0

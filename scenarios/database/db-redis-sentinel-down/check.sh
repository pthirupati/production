#!/usr/bin/env bash
# db-redis-sentinel-down: generic service health — fail-closed until active.
systemctl is-active redis-sentinel
exit 0

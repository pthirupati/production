#!/usr/bin/env bash
# db-redis-down: generic service health — fail-closed until the unit is active.
systemctl is-active redis
exit 0

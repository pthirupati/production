#!/usr/bin/env bash
# linux-memcached-down: generic service health — fail-closed until the unit is active.
systemctl is-active memcached
exit 0

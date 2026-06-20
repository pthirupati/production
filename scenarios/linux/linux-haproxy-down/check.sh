#!/usr/bin/env bash
# linux-haproxy-down: generic service health — fail-closed until the unit is active.
systemctl is-active haproxy
exit 0

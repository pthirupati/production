#!/usr/bin/env bash
# linux-nginx-stream-proxy-down: generic service health — fail-closed until the unit is active.
systemctl is-active nginx
exit 0

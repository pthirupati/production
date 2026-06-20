#!/usr/bin/env bash
# rhel-postfix-down: generic service health.
systemctl is-active postfix
exit 0

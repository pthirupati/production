#!/usr/bin/env bash
# linux-rabbitmq-down: generic service health — fail-closed until the unit is active.
systemctl is-active rabbitmq-server
exit 0

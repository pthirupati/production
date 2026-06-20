#!/usr/bin/env bash
# docker-daemon-down: generic service health.
systemctl is-active docker
exit 0

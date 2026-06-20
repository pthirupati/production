#!/usr/bin/env bash
# rhel-multipathd-down: generic service health.
systemctl is-active multipathd
exit 0

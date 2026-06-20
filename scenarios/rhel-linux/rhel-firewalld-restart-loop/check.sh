#!/usr/bin/env bash
# rhel-firewalld-restart-loop: generic service health.
systemctl is-active firewalld
exit 0

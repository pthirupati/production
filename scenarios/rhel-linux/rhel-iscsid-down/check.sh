#!/usr/bin/env bash
# rhel-iscsid-down: generic service health.
systemctl is-active iscsid
exit 0

#!/usr/bin/env bash
# rhel-auditd-down: generic service health — fail-closed until the unit is active.
systemctl is-active auditd
exit 0

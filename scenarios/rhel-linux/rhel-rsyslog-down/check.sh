#!/usr/bin/env bash
# rhel-rsyslog-down: generic service health — fail-closed until the unit is active.
systemctl is-active rsyslog
exit 0

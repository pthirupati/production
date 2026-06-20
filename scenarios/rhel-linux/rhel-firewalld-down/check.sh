#!/usr/bin/env bash
# rhel-firewalld-down: generic service health — fail-closed until the unit is active.
systemctl is-active firewalld
exit 0

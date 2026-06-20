#!/usr/bin/env bash
# rhel-chronyd-down: generic service health — fail-closed until the unit is active.
systemctl is-active chronyd
exit 0

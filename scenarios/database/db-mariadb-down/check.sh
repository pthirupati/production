#!/usr/bin/env bash
# db-mariadb-down: generic service health — fail-closed until the unit is active.
systemctl is-active mariadb
exit 0

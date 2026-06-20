#!/usr/bin/env bash
# db-pgbouncer-down: generic service health — fail-closed until the unit is active.
systemctl is-active pgbouncer
exit 0

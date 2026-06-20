#!/usr/bin/env bash
# db-postgres-standby-stopped: generic service health — fail-closed until active.
systemctl is-active postgresql
exit 0

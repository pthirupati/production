#!/usr/bin/env bash
# db-mysql-replica-stopped: generic service health — fail-closed until active.
systemctl is-active mysqld
exit 0

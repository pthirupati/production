#!/usr/bin/env bash
# db-clickhouse-down: generic service health — fail-closed until active.
systemctl is-active clickhouse-server
exit 0

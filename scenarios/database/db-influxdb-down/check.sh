#!/usr/bin/env bash
# db-influxdb-down: generic service health — fail-closed until active.
systemctl is-active influxdb
exit 0

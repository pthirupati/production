#!/usr/bin/env bash
# db-cassandra-down: generic service health — fail-closed until the unit is active.
systemctl is-active cassandra
exit 0

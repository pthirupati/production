#!/usr/bin/env bash
# db-mongodb-down: generic service health — fail-closed until the unit is active.
systemctl is-active mongod
exit 0

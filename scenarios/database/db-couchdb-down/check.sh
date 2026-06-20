#!/usr/bin/env bash
# db-couchdb-down: generic service health — fail-closed until active.
systemctl is-active couchdb
exit 0

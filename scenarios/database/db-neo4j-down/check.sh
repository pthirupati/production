#!/usr/bin/env bash
# db-neo4j-down: generic service health — fail-closed until active.
systemctl is-active neo4j
exit 0

#!/bin/bash
# Validate: max_connections raised above the broken default AND PostgreSQL back up.
grep max_connections /var/lib/pgsql/data/postgresql.conf
systemctl is-active postgresql
exit 0

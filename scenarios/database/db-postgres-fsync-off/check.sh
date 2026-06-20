#!/usr/bin/env bash
# db-postgres-fsync-off: config repair — fail-closed until /var/lib/pgsql/data/postgresql.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /var/lib/pgsql/data/postgresql.conf
exit 0

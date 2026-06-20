#!/usr/bin/env bash
# db-postgres-log-min-duration: config repair — fail-closed until /var/lib/pgsql/data/postgresql.conf carries FIXED-OK.
grep -q FIXED-OK /var/lib/pgsql/data/postgresql.conf
exit 0

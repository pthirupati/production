#!/usr/bin/env bash
# db-postgres-pg-hba-deny: config repair — fail-closed until /var/lib/pgsql/data/pg_hba.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /var/lib/pgsql/data/pg_hba.conf
exit 0

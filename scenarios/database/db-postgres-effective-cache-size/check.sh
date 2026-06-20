#!/usr/bin/env bash
# db-postgres-effective-cache-size: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/lib/pgsql/data/postgresql.conf
exit 0

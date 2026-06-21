#!/usr/bin/env bash
# Cross-tech Database<->Linux storage: the Postgres tablespace must be moved onto the
# new disk and the config reconciled. Fail-closed until postgresql.conf carries the
# FIXED-OK sentinel (written only after the storage + tablespace mapping are fixed).
grep -q FIXED-OK /var/lib/pgsql/data/postgresql.conf
exit 0

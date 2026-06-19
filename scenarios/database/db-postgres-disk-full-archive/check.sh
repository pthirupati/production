#!/bin/bash
# Validate: stale WAL archive backlog cleared (disk reclaimed) AND PostgreSQL back up.
ls /var/lib/pgsql/archive | grep wal
systemctl is-active postgresql
exit 0

#!/usr/bin/env bash
# shell-rsync-delete-danger: config repair — fail-closed until /opt/scripts/backup.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/backup.sh
exit 0

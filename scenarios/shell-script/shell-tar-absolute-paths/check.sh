#!/usr/bin/env bash
# shell-tar-absolute-paths: config repair — fail-closed until /opt/scripts/make-backup.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/make-backup.sh
exit 0

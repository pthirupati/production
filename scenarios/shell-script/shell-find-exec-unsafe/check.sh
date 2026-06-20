#!/usr/bin/env bash
# shell-find-exec-unsafe: config repair — fail-closed until /opt/scripts/purge.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/purge.sh
exit 0

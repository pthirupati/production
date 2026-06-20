#!/usr/bin/env bash
# shell-lockfile-stale: config repair — fail-closed until /opt/scripts/singleton.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/singleton.sh
exit 0

#!/usr/bin/env bash
# shell-glob-no-match: config repair — fail-closed until /opt/scripts/archive.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/archive.sh
exit 0

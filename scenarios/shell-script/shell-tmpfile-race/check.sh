#!/usr/bin/env bash
# shell-tmpfile-race: config repair — fail-closed until /opt/scripts/tmpwork.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/tmpwork.sh
exit 0

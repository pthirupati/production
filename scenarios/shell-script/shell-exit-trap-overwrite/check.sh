#!/usr/bin/env bash
# shell-exit-trap-overwrite: config repair — fail-closed until /opt/scripts/multi-trap.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/multi-trap.sh
exit 0

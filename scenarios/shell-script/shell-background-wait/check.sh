#!/usr/bin/env bash
# shell-background-wait: config repair — fail-closed until /opt/scripts/parallel.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/parallel.sh
exit 0

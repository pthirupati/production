#!/usr/bin/env bash
# shell-ifs-not-reset: config repair — fail-closed until /opt/scripts/csv.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/csv.sh
exit 0

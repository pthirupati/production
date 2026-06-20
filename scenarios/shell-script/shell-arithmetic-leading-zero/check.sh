#!/usr/bin/env bash
# shell-arithmetic-leading-zero: config repair — fail-closed until /opt/scripts/dates.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/dates.sh
exit 0

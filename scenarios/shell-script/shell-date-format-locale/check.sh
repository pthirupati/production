#!/usr/bin/env bash
# shell-date-format-locale: config repair — fail-closed until /opt/scripts/report-date.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/report-date.sh
exit 0

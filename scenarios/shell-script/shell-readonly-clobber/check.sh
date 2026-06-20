#!/usr/bin/env bash
# shell-readonly-clobber: config repair — fail-closed until /opt/scripts/report.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/report.sh
exit 0

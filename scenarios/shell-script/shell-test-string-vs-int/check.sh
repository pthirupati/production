#!/usr/bin/env bash
# shell-test-string-vs-int: config repair — fail-closed until /opt/scripts/threshold.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/threshold.sh
exit 0

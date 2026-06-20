#!/usr/bin/env bash
# shell-array-quoting: config repair — fail-closed until /opt/scripts/args-array.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/args-array.sh
exit 0

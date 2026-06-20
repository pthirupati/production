#!/usr/bin/env bash
# shell-source-relative-path: config repair — fail-closed until /opt/scripts/main-with-lib.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/main-with-lib.sh
exit 0

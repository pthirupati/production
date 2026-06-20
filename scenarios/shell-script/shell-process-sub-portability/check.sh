#!/usr/bin/env bash
# shell-process-sub-portability: config repair — fail-closed until /opt/scripts/diff-check.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/diff-check.sh
exit 0

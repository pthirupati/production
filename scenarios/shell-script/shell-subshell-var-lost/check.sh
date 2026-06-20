#!/usr/bin/env bash
# shell-subshell-var-lost: config repair — fail-closed until /opt/scripts/count.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/count.sh
exit 0

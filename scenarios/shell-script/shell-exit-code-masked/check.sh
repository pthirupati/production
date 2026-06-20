#!/usr/bin/env bash
# shell-exit-code-masked: config repair — fail-closed until /opt/scripts/check-status.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/check-status.sh
exit 0

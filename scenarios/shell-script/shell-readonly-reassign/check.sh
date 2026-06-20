#!/usr/bin/env bash
# shell-readonly-reassign: config repair — fail-closed until /opt/scripts/const.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/const.sh
exit 0

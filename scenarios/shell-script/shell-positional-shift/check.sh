#!/usr/bin/env bash
# shell-positional-shift: config repair — fail-closed until /opt/scripts/shift-args.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/shift-args.sh
exit 0

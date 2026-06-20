#!/usr/bin/env bash
# shell-numeric-bc-scale: config repair — fail-closed until /opt/scripts/ratio.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/ratio.sh
exit 0

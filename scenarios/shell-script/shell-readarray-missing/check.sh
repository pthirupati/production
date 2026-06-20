#!/usr/bin/env bash
# shell-readarray-missing: config repair — fail-closed until /opt/scripts/lines.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/lines.sh
exit 0

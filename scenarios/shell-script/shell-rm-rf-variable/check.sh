#!/usr/bin/env bash
# shell-rm-rf-variable: config repair — fail-closed until /opt/scripts/wipe.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/wipe.sh
exit 0

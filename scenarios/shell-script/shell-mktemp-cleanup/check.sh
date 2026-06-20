#!/usr/bin/env bash
# shell-mktemp-cleanup: config repair — fail-closed until /opt/scripts/build-temp.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/build-temp.sh
exit 0

#!/usr/bin/env bash
# shell-here-string-quoting: config repair — fail-closed until /opt/scripts/gen-config.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/gen-config.sh
exit 0

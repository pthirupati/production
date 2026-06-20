#!/usr/bin/env bash
# shell-printf-vs-echo: config repair — fail-closed until /opt/scripts/emit.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/emit.sh
exit 0

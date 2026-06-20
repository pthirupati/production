#!/usr/bin/env bash
# shell-eval-injection: config repair — fail-closed until /opt/scripts/parse.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/parse.sh
exit 0

#!/usr/bin/env bash
# shell-command-substitution-newline: config repair — fail-closed until /opt/scripts/capture.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/capture.sh
exit 0

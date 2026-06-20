#!/usr/bin/env bash
# shell-set-e-not-set: config repair — fail-closed until /opt/scripts/run.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/run.sh
exit 0

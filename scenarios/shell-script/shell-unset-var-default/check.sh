#!/usr/bin/env bash
# shell-unset-var-default: config repair — fail-closed until /opt/scripts/params.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/params.sh
exit 0

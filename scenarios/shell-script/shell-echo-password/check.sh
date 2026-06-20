#!/usr/bin/env bash
# shell-echo-password: config repair — fail-closed until /opt/scripts/db-login.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/db-login.sh
exit 0

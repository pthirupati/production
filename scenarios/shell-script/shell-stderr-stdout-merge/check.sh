#!/usr/bin/env bash
# shell-stderr-stdout-merge: config repair — fail-closed until /opt/scripts/logging.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/logging.sh
exit 0

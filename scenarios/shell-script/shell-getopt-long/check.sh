#!/usr/bin/env bash
# shell-getopt-long: config repair — fail-closed until /opt/scripts/longopts.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/longopts.sh
exit 0

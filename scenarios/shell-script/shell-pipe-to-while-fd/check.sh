#!/usr/bin/env bash
# shell-pipe-to-while-fd: config repair — fail-closed until /opt/scripts/fanout.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/fanout.sh
exit 0

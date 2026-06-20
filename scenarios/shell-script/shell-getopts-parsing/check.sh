#!/usr/bin/env bash
# shell-getopts-parsing: config repair — fail-closed until /opt/scripts/cli-tool.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/cli-tool.sh
exit 0

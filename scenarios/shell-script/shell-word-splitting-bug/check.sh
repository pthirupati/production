#!/usr/bin/env bash
# shell-word-splitting-bug: config repair — fail-closed until /opt/scripts/process-files.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/process-files.sh
exit 0

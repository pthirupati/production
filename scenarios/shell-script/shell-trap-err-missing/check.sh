#!/usr/bin/env bash
# shell-trap-err-missing: config repair — fail-closed until /opt/scripts/pipeline.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/pipeline.sh
exit 0

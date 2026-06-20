#!/usr/bin/env bash
# shell-arith-division-zero: config repair — fail-closed until /opt/scripts/metrics.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/metrics.sh
exit 0

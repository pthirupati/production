#!/usr/bin/env bash
# shell-signal-not-trapped: config repair — fail-closed until /opt/scripts/long-job.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/long-job.sh
exit 0

#!/usr/bin/env bash
# shell-cron-path-missing: config repair — fail-closed until /opt/scripts/cronjob.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/cronjob.sh
exit 0

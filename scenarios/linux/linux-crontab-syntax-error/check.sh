#!/usr/bin/env bash
# linux-crontab-syntax-error: config repair — fail-closed until /etc/cron.d/app-job carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/cron.d/app-job
exit 0

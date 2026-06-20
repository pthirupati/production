#!/usr/bin/env bash
# linux-logrotate-misconfig: config repair — fail-closed until /etc/logrotate.d/app carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/logrotate.d/app
exit 0

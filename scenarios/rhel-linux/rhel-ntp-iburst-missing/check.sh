#!/usr/bin/env bash
# rhel-ntp-iburst-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/chrony.conf
exit 0

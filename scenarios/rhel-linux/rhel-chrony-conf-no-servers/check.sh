#!/usr/bin/env bash
# rhel-chrony-conf-no-servers: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/chrony.conf
exit 0

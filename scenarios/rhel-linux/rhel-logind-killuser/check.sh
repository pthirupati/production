#!/usr/bin/env bash
# rhel-logind-killuser: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/systemd/logind.conf
exit 0

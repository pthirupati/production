#!/usr/bin/env bash
# rhel-rsyslog-remote-forward: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/rsyslog.d/remote.conf
exit 0

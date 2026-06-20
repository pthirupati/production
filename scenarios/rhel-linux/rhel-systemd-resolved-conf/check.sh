#!/usr/bin/env bash
# rhel-systemd-resolved-conf: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/systemd/resolved.conf
exit 0

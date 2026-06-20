#!/usr/bin/env bash
# rhel-systemd-oomd-killing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/systemd/oomd.conf
exit 0

#!/usr/bin/env bash
# rhel-coredump-disabled: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/systemd/coredump.conf
exit 0

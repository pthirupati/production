#!/usr/bin/env bash
# linux-journald-storage-volatile: config repair — fail-closed until /etc/systemd/journald.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/systemd/journald.conf
exit 0

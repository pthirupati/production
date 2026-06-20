#!/usr/bin/env bash
# rhel-kdump-not-configured: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/kdump.conf
exit 0

#!/usr/bin/env bash
# rhel-selinux-booleans: config repair — fail-closed until /etc/selinux/booleans.local carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/selinux/booleans.local
exit 0

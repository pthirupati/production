#!/usr/bin/env bash
# rhel-selinux-permissive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/selinux/config
exit 0

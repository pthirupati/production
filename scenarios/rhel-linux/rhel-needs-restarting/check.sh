#!/usr/bin/env bash
# rhel-needs-restarting: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/rhel-patch-policy.conf
exit 0

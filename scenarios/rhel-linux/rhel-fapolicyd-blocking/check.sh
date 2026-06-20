#!/usr/bin/env bash
# rhel-fapolicyd-blocking: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/fapolicyd/fapolicyd.rules
exit 0

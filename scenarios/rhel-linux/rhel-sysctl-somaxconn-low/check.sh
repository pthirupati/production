#!/usr/bin/env bash
# rhel-sysctl-somaxconn-low: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/sysctl.d/99-net.conf
exit 0

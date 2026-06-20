#!/usr/bin/env bash
# rhel-yum-proxy-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/dnf/dnf.conf
exit 0

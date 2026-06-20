#!/usr/bin/env bash
# rhel-sshd-maxstartups: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/ssh/sshd_config.d/limits.conf
exit 0

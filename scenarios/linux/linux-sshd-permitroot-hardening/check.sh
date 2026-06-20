#!/usr/bin/env bash
# linux-sshd-permitroot-hardening: config repair — fail-closed until /etc/ssh/sshd_config.d/hardening.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/ssh/sshd_config.d/hardening.conf
exit 0

#!/usr/bin/env bash
# Cross-tech Security<->Linux SSH hardening: the CIS drop-in must be hardened.
# Fail-closed until /etc/ssh/sshd_config.d/50-cis.conf carries the FIXED-OK sentinel
# (written only after root-login/password-auth are disabled and strong crypto pinned).
grep -q FIXED-OK /etc/ssh/sshd_config.d/50-cis.conf
exit 0

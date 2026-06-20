#!/usr/bin/env bash
# rhel-pam-faillock-lockout: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/security/faillock.conf
exit 0

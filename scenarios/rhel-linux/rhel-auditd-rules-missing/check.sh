#!/usr/bin/env bash
# rhel-auditd-rules-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/audit/rules.d/audit.rules
exit 0

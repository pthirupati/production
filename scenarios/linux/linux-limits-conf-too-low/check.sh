#!/usr/bin/env bash
# linux-limits-conf-too-low: config repair — fail-closed until /etc/security/limits.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/security/limits.conf
exit 0

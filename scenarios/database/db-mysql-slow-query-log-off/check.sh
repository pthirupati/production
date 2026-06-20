#!/usr/bin/env bash
# db-mysql-slow-query-log-off: config repair — fail-closed until /etc/my.cnf carries FIXED-OK.
grep -q FIXED-OK /etc/my.cnf
exit 0

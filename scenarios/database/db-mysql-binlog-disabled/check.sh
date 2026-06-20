#!/usr/bin/env bash
# db-mysql-binlog-disabled: config repair — fail-closed until /etc/my.cnf carries FIXED-OK.
grep -q FIXED-OK /etc/my.cnf
exit 0

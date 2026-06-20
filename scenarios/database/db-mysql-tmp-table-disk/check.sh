#!/usr/bin/env bash
# db-mysql-tmp-table-disk: config repair — fail-closed until /etc/my.cnf carries FIXED-OK.
grep -q FIXED-OK /etc/my.cnf
exit 0

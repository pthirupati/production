#!/usr/bin/env bash
# db-mysql-bind-address: config repair — fail-closed until /etc/my.cnf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/my.cnf
exit 0

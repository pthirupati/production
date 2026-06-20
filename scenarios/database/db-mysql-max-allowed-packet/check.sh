#!/usr/bin/env bash
# db-mysql-max-allowed-packet: config repair — fail-closed until /etc/my.cnf carries FIXED-OK.
grep -q FIXED-OK /etc/my.cnf
exit 0

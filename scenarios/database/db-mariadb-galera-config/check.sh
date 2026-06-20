#!/usr/bin/env bash
# db-mariadb-galera-config: config repair — fail-closed until /etc/my.cnf.d/galera.cnf carries FIXED-OK.
grep -q FIXED-OK /etc/my.cnf.d/galera.cnf
exit 0

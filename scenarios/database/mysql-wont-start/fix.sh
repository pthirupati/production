#!/bin/bash
set -e
sed -i 's/999999G/128M/g' /etc/mysql/mysql.conf.d/mysqld.cnf 2>/dev/null || true
service mysql restart 2>/dev/null || systemctl restart mysql 2>/dev/null || true

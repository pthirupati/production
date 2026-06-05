#!/bin/bash
if service mysql start 2>/dev/null || systemctl start mysql 2>/dev/null; then
  sleep 2
fi
if mysqladmin ping 2>/dev/null | grep -q alive; then
  echo "OK: MySQL running"
  exit 0
fi
if grep -q '999999G' /etc/mysql/mysql.conf.d/mysqld.cnf 2>/dev/null; then
  echo "FAIL: invalid innodb_buffer_pool_size — reduce to realistic value (e.g. 128M)"
  exit 1
fi
echo "FAIL: MySQL not running — check error log"
exit 1

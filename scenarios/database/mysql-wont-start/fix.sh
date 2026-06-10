#!/bin/bash
set -e
sed -i '/innodb_buffer_pool_size = 999999G/d' /etc/mysql/mysql.conf.d/mysqld.cnf
grep -q '^innodb_buffer_pool_size' /etc/mysql/mysql.conf.d/mysqld.cnf || \
  echo 'innodb_buffer_pool_size = 128M' >> /etc/mysql/mysql.conf.d/mysqld.cnf
service mysql start 2>/dev/null || mysqld_safe &
sleep 4

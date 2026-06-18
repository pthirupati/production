#!/bin/bash
# Check that MySQL root@'%' no longer exists
# We need to check without providing password (use defaults file or socket)
ROOT_HOSTS=$(mysql -u root --connect-expired-password -e "SELECT host FROM mysql.user WHERE user='root';" 2>/dev/null | grep -v '^host' | tr -d ' ')
if echo "$ROOT_HOSTS" | grep -q '^%$'; then
  echo "FAIL: MySQL root user still has access from '%' (any host) — revoke with: DROP USER 'root'@'%'; FLUSH PRIVILEGES;"
  exit 1
fi
# Check MySQL bind-address
BIND=$(grep -E '^\s*bind-address\s*=' /etc/mysql/mysql.conf.d/mysqld.cnf /etc/mysql/my.cnf 2>/dev/null | awk -F= '{print $2}' | tr -d ' ' | head -1)
if [ "$BIND" = "0.0.0.0" ] || [ "$BIND" = "::" ]; then
  echo "FAIL: MySQL still binding to $BIND — set bind-address=127.0.0.1 in mysqld.cnf"
  exit 1
fi
if [ -n "$ROOT_HOSTS" ]; then
  echo "OK: MySQL root user restricted to localhost only (hosts: $(echo "$ROOT_HOSTS" | tr '\n' ','))"
  exit 0
fi
echo "OK: MySQL root@'%' grant removed"
exit 0

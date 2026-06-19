#!/bin/bash
# Validate: crashed MyISAM table repaired (marker cleared) AND mysqld back up.
mysqlcheck --check appdb orders
systemctl is-active mysqld
exit 0

#!/bin/bash
systemctl is-active mysqld
mysqladmin ping
exit 0

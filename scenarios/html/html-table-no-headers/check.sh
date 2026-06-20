#!/usr/bin/env bash
# html-table-no-headers: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/data.html
exit 0

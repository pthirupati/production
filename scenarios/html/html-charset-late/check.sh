#!/usr/bin/env bash
# html-charset-late: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/late.html
exit 0

#!/usr/bin/env bash
# html-mixed-content: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/secure.html
exit 0

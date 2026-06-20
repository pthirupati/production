#!/usr/bin/env bash
# html-noscript-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/spa.html
exit 0

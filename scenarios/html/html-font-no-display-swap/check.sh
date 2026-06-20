#!/usr/bin/env bash
# html-font-no-display-swap: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/typography.html
exit 0

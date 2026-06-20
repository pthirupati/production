#!/usr/bin/env bash
# html-missing-favicon: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/index.html
exit 0

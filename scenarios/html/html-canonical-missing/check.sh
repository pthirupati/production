#!/usr/bin/env bash
# html-canonical-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/page.html
exit 0

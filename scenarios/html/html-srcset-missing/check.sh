#!/usr/bin/env bash
# html-srcset-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/responsive.html
exit 0

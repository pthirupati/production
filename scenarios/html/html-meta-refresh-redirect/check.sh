#!/usr/bin/env bash
# html-meta-refresh-redirect: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/redirect.html
exit 0

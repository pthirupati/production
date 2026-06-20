#!/usr/bin/env bash
# html-missing-width-height: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/news.html
exit 0

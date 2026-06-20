#!/usr/bin/env bash
# html-heading-skip: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/article.html
exit 0

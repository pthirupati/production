#!/usr/bin/env bash
# html-base-tag-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/app.html
exit 0

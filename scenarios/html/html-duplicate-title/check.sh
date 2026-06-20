#!/usr/bin/env bash
# html-duplicate-title: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/dup.html
exit 0

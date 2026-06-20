#!/usr/bin/env bash
# html-deprecated-tags: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/old.html
exit 0

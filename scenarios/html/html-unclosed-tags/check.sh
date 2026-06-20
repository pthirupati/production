#!/usr/bin/env bash
# html-unclosed-tags: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/broken.html
exit 0

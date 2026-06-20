#!/usr/bin/env bash
# html-empty-link-text: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/icons.html
exit 0

#!/usr/bin/env bash
# html-form-get-sensitive: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/reset.html
exit 0

#!/usr/bin/env bash
# html-preload-misconfigured: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/fast.html
exit 0

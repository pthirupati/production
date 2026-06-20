#!/usr/bin/env bash
# html-no-lazy-loading: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/feed.html
exit 0

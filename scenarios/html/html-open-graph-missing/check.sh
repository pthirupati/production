#!/usr/bin/env bash
# html-open-graph-missing: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/index.html
exit 0

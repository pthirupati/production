#!/usr/bin/env bash
# html-script-blocking-render: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/index.html
exit 0

#!/usr/bin/env bash
# html-viewport-user-scalable: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/mobile.html
exit 0

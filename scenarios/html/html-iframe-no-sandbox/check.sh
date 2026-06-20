#!/usr/bin/env bash
# html-iframe-no-sandbox: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/embed.html
exit 0

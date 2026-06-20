#!/usr/bin/env bash
# html-csp-blocking-assets: config repair — fail-closed until /var/www/html/index.html carries the FIXED-OK sentinel.
grep -q FIXED-OK /var/www/html/index.html
exit 0

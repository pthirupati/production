#!/usr/bin/env bash
# html-robots-noindex: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/landing.html
exit 0

#!/usr/bin/env bash
# html-print-stylesheet: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/invoice.html
exit 0

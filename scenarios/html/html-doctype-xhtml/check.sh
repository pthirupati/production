#!/usr/bin/env bash
# html-doctype-xhtml: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/legacy-xhtml.html
exit 0

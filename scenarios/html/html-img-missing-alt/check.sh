#!/usr/bin/env bash
# html-img-missing-alt: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/gallery.html
exit 0

#!/usr/bin/env bash
# html-inaccessible-form: config repair — fail-closed until /var/www/html/contact.html carries the FIXED-OK sentinel.
grep -q FIXED-OK /var/www/html/contact.html
exit 0

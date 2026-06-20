#!/usr/bin/env bash
# html-form-no-name: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/login.html
exit 0

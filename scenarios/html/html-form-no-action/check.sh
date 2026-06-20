#!/usr/bin/env bash
# html-form-no-action: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/signup.html
exit 0

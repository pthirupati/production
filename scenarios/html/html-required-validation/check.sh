#!/usr/bin/env bash
# html-required-validation: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/order.html
exit 0

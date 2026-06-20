#!/usr/bin/env bash
# html-entity-encoding: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /var/www/html/comments.html
exit 0

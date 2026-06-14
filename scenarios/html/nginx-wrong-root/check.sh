#!/bin/bash
# Simulation validation — document root must point to /var/www/html
nginx -t 2>/dev/null || exit 1
grep -q 'root /var/www/html' /etc/nginx/sites-enabled/default || exit 1
pgrep -x nginx > /dev/null || exit 1
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
[ "$HTTP_CODE" = "200" ] || exit 1
exit 0

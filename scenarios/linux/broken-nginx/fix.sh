#!/bin/bash
set -e
sed -i 's/listn 80/listen 80/' /etc/nginx/sites-available/default 2>/dev/null || true
mkdir -p /run/nginx /var/log/nginx /var/cache/nginx
nginx -t
pkill nginx 2>/dev/null || true
nginx

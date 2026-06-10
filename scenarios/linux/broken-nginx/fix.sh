#!/bin/bash
set -e
mkdir -p /etc/nginx /etc/nginx/conf.d
cat > /etc/nginx/nginx.conf <<'EOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  sendfile on;
  keepalive_timeout 65;
  include /etc/nginx/conf.d/*.conf;
}
EOF
cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
  listen 80 default_server;
  server_name _;
  location / {
    return 200 'ok';
    add_header Content-Type text/plain;
  }
}
EOF
nginx -t
service nginx restart 2>/dev/null || systemctl restart nginx 2>/dev/null || (nginx -s stop 2>/dev/null || true; nginx)

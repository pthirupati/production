#!/bin/bash
set -e
chattr -i /etc/myapp/config.env 2>/dev/null || true
mkdir -p /etc/myapp
if grep -q '^PORT=' /etc/myapp/config.env 2>/dev/null; then
  sed -i 's/^PORT=.*/PORT=9090/' /etc/myapp/config.env
else
  echo 'PORT=9090' >> /etc/myapp/config.env
fi

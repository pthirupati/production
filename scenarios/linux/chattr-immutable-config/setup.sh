#!/bin/bash
# Apply immutable flag at container start (not during image build).
mkdir -p /etc/myapp
echo 'PORT=8080' > /etc/myapp/config.env
chattr +i /etc/myapp/config.env 2>/dev/null || true

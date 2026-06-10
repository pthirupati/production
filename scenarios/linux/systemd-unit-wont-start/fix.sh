#!/bin/bash
set -e
sed -i 's#^ExecStart=.*#ExecStart=/opt/myapp/run.sh#' /etc/systemd/system/myapp.service
systemctl daemon-reload 2>/dev/null || true
systemctl restart myapp 2>/dev/null || true

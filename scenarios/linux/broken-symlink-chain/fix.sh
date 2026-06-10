#!/bin/bash
set -e
ln -sfn /opt/app/bin/real.sh /usr/local/bin/apptool
chmod +x /opt/app/bin/real.sh 2>/dev/null || true

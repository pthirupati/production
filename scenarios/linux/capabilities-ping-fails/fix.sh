#!/bin/bash
set -e
PING=$(readlink -f "$(command -v ping)")
if setcap cap_net_raw+ep "$PING" 2>/dev/null; then
  exit 0
fi
# overlayfs may block setcap — copy to tmpfs and bind-mount over ping
TMP=/tmp/ping.cap
cp -a "$PING" "$TMP"
setcap cap_net_raw+ep "$TMP"
mount --bind "$TMP" "$PING"

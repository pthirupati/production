#!/bin/bash
# Copy shared lab helpers into a scenario directory
# Usage: ./scenarios/shared/copy-helpers.sh scenarios/linux/my-scenario
set -euo pipefail
DEST="${1:?usage: copy-helpers.sh <scenario-dir>}"
SRC="$(dirname "$0")"
cp "$SRC/systemctl.py" "$DEST/"
cp "$SRC/service.sh" "$DEST/"
chmod +x "$DEST/service.sh"
if [ -f "$SRC/lab-loop.sh" ]; then
  cp "$SRC/lab-loop.sh" "$DEST/"
  chmod +x "$DEST/lab-loop.sh"
fi
if [ -f "$SRC/lab-dnsmasq.sh" ]; then
  cp "$SRC/lab-dnsmasq.sh" "$DEST/"
  chmod +x "$DEST/lab-dnsmasq.sh"
fi

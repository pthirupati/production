#!/bin/bash
# Copy shared lab helpers into a scenario directory
# Usage: ./scenarios/shared/copy-helpers.sh scenarios/linux/my-scenario
set -euo pipefail
DEST="${1:?usage: copy-helpers.sh <scenario-dir>}"
SRC="$(dirname "$0")"
cp "$SRC/systemctl.py" "$DEST/"
cp "$SRC/service.sh" "$DEST/"
chmod +x "$DEST/service.sh"

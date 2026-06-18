#!/bin/bash
# Check that the SUID bit has been removed from python3
PYTHON_BIN=$(command -v python3 2>/dev/null || echo "/usr/bin/python3")
if [ ! -f "$PYTHON_BIN" ]; then
  echo "FAIL: python3 not found at expected path — check /usr/bin/python3"
  exit 1
fi
# Check if SUID bit is still set
if [ -u "$PYTHON_BIN" ]; then
  PERMS=$(ls -la "$PYTHON_BIN" | awk '{print $1}')
  echo "FAIL: SUID bit is still set on $PYTHON_BIN ($PERMS) — remove with: chmod u-s $PYTHON_BIN"
  exit 1
fi
echo "OK: SUID bit removed from $PYTHON_BIN"
exit 0

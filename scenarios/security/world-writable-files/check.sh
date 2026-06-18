#!/bin/bash
# Check that no world-writable files exist in /etc
WORLD_WRITABLE=$(find /etc -perm -o+w -type f 2>/dev/null)
if [ -z "$WORLD_WRITABLE" ]; then
  echo "OK: no world-writable files found in /etc"
  exit 0
fi
COUNT=$(echo "$WORLD_WRITABLE" | wc -l)
echo "FAIL: found $COUNT world-writable file(s) in /etc:"
echo "$WORLD_WRITABLE" | head -10
echo "Fix with: find /etc -perm -o+w -type f -exec chmod o-w {} \\;"
exit 1

#!/bin/bash
# Check that Apache directory listing is disabled
# First check that 'Options Indexes' (enabling listing) is not active
if grep -rE '^\s*Options.*\bIndexes\b' /etc/apache2/ 2>/dev/null | grep -v '\-Indexes' | grep -qv '^#'; then
  echo "FAIL: Apache has 'Options Indexes' enabled — change to 'Options -Indexes' to disable directory listing"
  exit 1
fi
# Check Apache is running
if ! systemctl is-active --quiet apache2 2>/dev/null; then
  echo "FAIL: Apache2 is not running — start with: systemctl start apache2"
  exit 1
fi
# Functional check — directory listing should not be served
LISTING=$(curl -sf --max-time 5 http://localhost/ 2>/dev/null | grep -ci 'Index of\|Directory listing')
if [ "$LISTING" -gt 0 ]; then
  echo "FAIL: Apache is still serving directory listings — reload after fixing: systemctl reload apache2"
  exit 1
fi
echo "OK: Apache directory listing is disabled"
exit 0

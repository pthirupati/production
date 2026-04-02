#!/bin/bash
# Validation for "Disk Space Crisis"
# The user must:
#   1. Find and remove the large log file (100MB)
#   2. Find and remove the hidden cache file (50MB)
#   3. Kill the log_generator process that keeps growing the log

FAILED=0

# Check 1: The large log file must be removed or shrunk below 1MB
WEBAPP_LOG="/var/log/webapp/application.log"
if [ -f "$WEBAPP_LOG" ]; then
    SIZE=$(stat -c%s "$WEBAPP_LOG" 2>/dev/null || stat -f%z "$WEBAPP_LOG" 2>/dev/null)
    if [ "$SIZE" -gt 1048576 ]; then
        echo "FAIL: /var/log/webapp/application.log is still too large (${SIZE} bytes). Remove or truncate it."
        FAILED=1
    else
        echo "OK: application.log is under 1MB"
    fi
else
    echo "OK: application.log has been removed"
fi

# Check 2: The hidden cache file must be removed
HIDDEN_CACHE="/tmp/.hidden_cache/cache.dat"
if [ -f "$HIDDEN_CACHE" ]; then
    echo "FAIL: Hidden cache file /tmp/.hidden_cache/cache.dat still exists. Find and remove it."
    FAILED=1
else
    echo "OK: Hidden cache file has been removed"
fi

# Check 3: The log_generator process must be killed
if pgrep -f log_generator.sh > /dev/null 2>&1; then
    echo "FAIL: The log_generator process is still running. Kill it to stop disk usage growth."
    FAILED=1
else
    echo "OK: log_generator process is not running"
fi

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "RESULT: Not all checks passed. Keep trying!"
    exit 1
fi

echo ""
echo "PASS: Disk space cleaned up successfully! All large files removed and log generator stopped."
exit 0

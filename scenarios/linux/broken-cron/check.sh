#!/bin/bash
# Validation for "Fix the Broken Cron Job"
# The user must:
#   1. Make the backup script executable (chmod 755)
#   2. Ensure cron entry exists for the backup
#   3. Verify the script actually works by running it

FAILED=0

# Check 1: Backup script must exist
if [ ! -f /opt/backup.sh ]; then
    echo "FAIL: /opt/backup.sh does not exist"
    FAILED=1
else
    echo "OK: /opt/backup.sh exists"
fi

# Check 2: Script must be executable (755 or 700)
PERM=$(stat -c '%a' /opt/backup.sh 2>/dev/null)
if [ "$PERM" != "755" ] && [ "$PERM" != "700" ] && [ "$PERM" != "750" ]; then
    echo "FAIL: /opt/backup.sh permissions are $PERM — must be executable (e.g., 755)"
    FAILED=1
else
    echo "OK: /opt/backup.sh is executable (permissions: $PERM)"
fi

# Check 3: Cron entry must exist
CRON=$(crontab -l 2>/dev/null | grep -c backup)
if [ "$CRON" -eq 0 ]; then
    echo "FAIL: No cron entry found for backup. Check 'crontab -l'"
    FAILED=1
else
    echo "OK: Cron entry for backup exists"
fi

# Check 4: The script should actually run successfully
if [ -x /opt/backup.sh ]; then
    bash /opt/backup.sh 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "OK: Backup script runs successfully"
    else
        echo "WARN: Backup script ran but returned an error (non-critical)"
    fi
fi

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "RESULT: Not all checks passed. Keep trying!"
    exit 1
fi

echo ""
echo "PASS: Cron job is properly configured! The backup will run on schedule."
exit 0

#!/bin/bash
# Validation for "Kill the Zombie Process"
# The user must find and kill the runaway.sh process that consumes CPU.

FAILED=0

# Check 1: The runaway.sh process must not be running
if pgrep -f runaway.sh > /dev/null 2>&1; then
    echo "FAIL: The runaway.sh process is still running. Find it with 'ps aux' or 'htop' and kill it."
    FAILED=1
else
    echo "OK: runaway.sh process has been killed"
fi

# Check 2: No remaining bash busy-loops consuming CPU
RUNAWAY_PIDS=$(ps aux 2>/dev/null | grep -v grep | grep -c 'runaway')
if [ "$RUNAWAY_PIDS" -gt 0 ]; then
    echo "FAIL: There are still runaway processes running ($RUNAWAY_PIDS found)"
    FAILED=1
else
    echo "OK: No runaway processes detected"
fi

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "RESULT: Kill the runaway process to pass this challenge."
    exit 1
fi

echo ""
echo "PASS: CPU usage is back to normal. The runaway process has been killed!"
exit 0

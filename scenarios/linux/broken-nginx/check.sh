#!/bin/bash
# Validation script for "Fix the Broken Nginx Server"
# Exit 0 = pass, Exit 1 = fail
# The user MUST fix the config AND start the service themselves.

# Step 1: Check that the nginx configuration is valid
nginx -t 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: nginx configuration is invalid. Fix the config first."
    exit 1
fi
echo "OK: nginx configuration syntax is valid"

# Step 2: Check that nginx is actually running (user must start it)
if ! pgrep -x nginx > /dev/null 2>&1; then
    echo "FAIL: nginx is not running. Start the service after fixing the config."
    exit 1
fi
echo "OK: nginx process is running"

# Step 3: Check that port 80 is responding with HTTP 200
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL: nginx is not responding on port 80 (got HTTP $HTTP_CODE)"
    exit 1
fi

echo "PASS: nginx is running and responding correctly on port 80"
exit 0

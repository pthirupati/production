#!/bin/bash
nginx -t 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: nginx configuration is invalid"
    exit 1
fi
if ! pgrep -x nginx > /dev/null 2>&1; then
    echo "FAIL: nginx is not running"
    exit 1
fi
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL: nginx not responding on port 80 (got HTTP $HTTP_CODE)"
    exit 1
fi
echo "PASS"
exit 0

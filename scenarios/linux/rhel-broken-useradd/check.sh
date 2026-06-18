#!/bin/bash
pwck 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: passwd/group files still have errors"
    exit 1
fi
getent passwd appuser > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "FAIL: appuser does not exist"
    exit 1
fi
echo "PASS"
exit 0

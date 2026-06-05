#!/bin/bash
stat -c %a /tmp/app | grep -q 1777 && echo PASS && exit 0
[ "$(stat -c %a /tmp/app)" = "1777" ] && echo PASS && exit 0
PERM=$(stat -c %A /tmp/app)
echo "$PERM" | grep -q 't' && echo PASS && exit 0
echo FAIL: chmod 1777 /tmp/app (sticky bit)
exit 1

#!/bin/bash
PERM=$(stat -c %a /usr/local/bin/reads-shadow)
[[ "$PERM" == *4* ]] || stat -c %A /usr/local/bin/reads-shadow | grep -q s && echo PASS && exit 0
echo FAIL: chmod u+s /usr/local/bin/reads-shadow (SUID bit)
exit 1

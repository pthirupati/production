#!/bin/bash
P1=$(stat -c %a /home/dev/.ssh)
P2=$(stat -c %a /home/dev/.ssh/authorized_keys)
[ "$P1" = "700" ] && [ "$P2" = "600" ] && echo PASS && exit 0
echo FAIL: fix ~/.ssh to 700 and authorized_keys to 600
exit 1

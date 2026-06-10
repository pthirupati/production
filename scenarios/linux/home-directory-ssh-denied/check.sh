#!/bin/bash
P=$(stat -c %a /home/ops)
[ "$P" = "755" ] || [ "$P" = "750" ] || [ "$P" = "700" ] && echo PASS && exit 0
echo "FAIL: chmod 755 /home/ops (remove world-writable)"
exit 1

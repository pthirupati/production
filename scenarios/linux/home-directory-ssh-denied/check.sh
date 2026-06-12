#!/bin/bash
P=$(stat -c %a /home/ops 2>/dev/null)
[ "$P" = "777" ] && { echo "FAIL: /home/ops is world-writable (mode 777) — chmod 755 /home/ops"; exit 1; }
[ "$P" = "755" ] || [ "$P" = "750" ] || [ "$P" = "700" ] && echo PASS && exit 0
echo "FAIL: chmod 755 /home/ops (remove world-writable)"
exit 1

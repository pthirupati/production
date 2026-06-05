#!/bin/bash
PING=$(command -v ping)
getcap "$PING" 2>/dev/null | grep -q cap_net_raw && echo PASS && exit 0
echo FAIL: setcap cap_net_raw+ep $PING
exit 1

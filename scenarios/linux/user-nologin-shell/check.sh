#!/bin/bash
SHELL=$(getent passwd deploy | cut -d: -f7)
[ "$SHELL" = "/bin/bash" ] || [ "$SHELL" = "/bin/sh" ] && echo PASS && exit 0
echo FAIL: usermod -s /bin/bash deploy
exit 1

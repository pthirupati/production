#!/bin/bash
GID=$(getent passwd baduser | cut -d: -f4)
getent group "$GID" >/dev/null && echo PASS && exit 0
echo FAIL: usermod -g devteam baduser (or create missing group)
exit 1

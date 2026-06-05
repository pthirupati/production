#!/bin/bash
/usr/local/bin/apptool >/dev/null 2>&1 && echo PASS && exit 0
echo FAIL: fix symlink: ln -sf /opt/app/bin/real.sh /usr/local/bin/apptool
exit 1

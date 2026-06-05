#!/bin/bash
/usr/local/bin/myapp 2>/dev/null && echo PASS && exit 0
ldconfig -p 2>/dev/null | grep -q libfixit && /usr/local/bin/myapp && echo PASS && exit 0
echo FAIL: restore /etc/ld.so.conf.d/fixitlab.conf and run ldconfig
exit 1

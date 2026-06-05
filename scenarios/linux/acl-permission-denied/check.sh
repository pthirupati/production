#!/bin/bash
getfacl /srv/shared 2>/dev/null | grep -q 'user:alice' && echo PASS && exit 0
echo FAIL: setfacl -m u:alice:rwx /srv/shared
exit 1

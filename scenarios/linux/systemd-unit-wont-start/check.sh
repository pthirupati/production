#!/bin/bash
grep -q 'ExecStart=/opt/myapp/run.sh' /etc/systemd/system/myapp.service && echo PASS && exit 0
echo FAIL: fix ExecStart in /etc/systemd/system/myapp.service to /opt/myapp/run.sh
exit 1

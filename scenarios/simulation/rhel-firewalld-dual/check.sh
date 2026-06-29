#!/bin/bash
firewall-cmd --list-ports | grep -q 80/tcp
pgrep -x nginx
exit 0

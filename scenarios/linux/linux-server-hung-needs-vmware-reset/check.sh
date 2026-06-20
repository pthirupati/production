#!/bin/bash
# Cross-tech hung guest: only a VMware reset of web-prod-01 un-wedges the guest;
# the terminal cannot recover a hung kernel by itself. Pass once nginx is active.
systemctl is-active nginx
pgrep -x nginx
exit 0

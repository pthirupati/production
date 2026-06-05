#!/bin/bash
grep -q '^hosts:.*files' /etc/nsswitch.conf && ! grep -q 'myhostname' /etc/nsswitch.conf && echo PASS && exit 0
echo FAIL: fix /etc/nsswitch.conf hosts line to: hosts: files dns
exit 1

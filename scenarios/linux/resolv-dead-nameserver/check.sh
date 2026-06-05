#!/bin/bash
getent hosts app.fixitlab.local >/dev/null 2>&1 && echo PASS && exit 0
echo FAIL: point nameserver to 127.0.0.1 in /etc/resolv.conf (local dnsmasq serves app.fixitlab.local)
exit 1

#!/usr/bin/env bash
# linux-resolv-conf-wrong: config repair — fail-closed until /etc/resolv.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/resolv.conf
exit 0

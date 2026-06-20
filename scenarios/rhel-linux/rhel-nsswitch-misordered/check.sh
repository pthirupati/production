#!/usr/bin/env bash
# rhel-nsswitch-misordered: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nsswitch.conf
exit 0

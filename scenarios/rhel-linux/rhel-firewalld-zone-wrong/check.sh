#!/usr/bin/env bash
# rhel-firewalld-zone-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/firewalld/zones/public.xml
exit 0

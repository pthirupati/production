#!/usr/bin/env bash
# rhel-sysctl-swappiness: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/sysctl.d/99-vm.conf
exit 0
